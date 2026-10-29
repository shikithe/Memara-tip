#!/usr/bin/env python3
"""Prepare a read-only MEMARASIX analyst queue from collector JSON.

Does not predict, select bet legs, fetch odds, modify the bank or publish tickets.
"""
import argparse
import json
from datetime import datetime, timezone, time, timedelta
from zoneinfo import ZoneInfo

SARAJEVO = ZoneInfo('Europe/Sarajevo')

def fixture_window(day):
    """Daily sports selection: 10:00 local today through 09:00 local tomorrow (exclusive)."""
    base = datetime.fromisoformat(day).date()
    start = datetime.combine(base, time(10, 0), tzinfo=SARAJEVO)
    end = datetime.combine(base + timedelta(days=1), time(9, 0), tzinfo=SARAJEVO)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)

def fixture_in_window(fixture, start, end):
    if fixture.get('sport') not in ('football', 'basketball') or fixture.get('status') != 'pre':
        return False
    try:
        tipoff = datetime.fromisoformat(fixture['start_utc'].replace('Z', '+00:00'))
        return tipoff.tzinfo is not None and start <= tipoff.astimezone(timezone.utc) < end
    except (KeyError, ValueError, TypeError):
        return False
from pathlib import Path

def build(data, max_football=None, max_nba=12, next_nba=None):
    fixtures = data.get("fixtures", [])
    if not isinstance(fixtures, list):
        raise ValueError("fixtures must be an array")
    window_start, window_end = fixture_window(data["date"])
    all_rows = list(fixtures)
    if next_nba:
        all_rows.extend(next_nba.get("fixtures", []))
    now = datetime.now(timezone.utc)
    upcoming = [f for f in all_rows if fixture_in_window(f, window_start, window_end)
                and datetime.fromisoformat(f["start_utc"].replace("Z", "+00:00")) > now]
    # Deduplicate across both Sarajevo calendar days and providers.
    unique = {}
    for f in upcoming:
        key = (f["sport"], f.get("league", ""), f.get("home", ""), f.get("away", ""), f["start_utc"])
        if key not in unique or (f.get("provider") == "rezultati.com-mobile-public" and unique[key].get("provider") != "rezultati.com-mobile-public"):
            unique[key] = f
    football = [f for f in unique.values() if f["sport"] == "football"]
    nba = [f for f in unique.values() if f["sport"] == "basketball" and f.get("league") == "nba"]
    football.sort(key=lambda f: (0 if f.get("provider") == "rezultati.com-mobile-public" else 1, f.get("start_utc", "")))
    selected_football = football if max_football is None else football[:max_football]
    nba.sort(key=lambda f: f["start_utc"])
    players = data.get("nba_players", [])
    return {
        "schema_version": "1.0",
        "date": data.get("date"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "state": "awaiting_human_or_AI_analysis",
        "not_betting_advice": True,
        "odds_verified": False,
        "bank_modified": False,
        "tickets_published": False,
        "source_status": data.get("status"),
        "source_errors": data.get("errors", []),
        "scope_warning": "Partial coverage, especially TheSportsDB regional free league endpoints.",
        "football_candidates": selected_football,
        "nba_games": nba[:max_nba],
        "window_sarajevo": {"start": window_start.astimezone(SARAJEVO).isoformat(), "end_exclusive": window_end.astimezone(SARAJEVO).isoformat()},
        "nba_window_sarajevo": {"start": window_start.astimezone(SARAJEVO).isoformat(), "end_exclusive": window_end.astimezone(SARAJEVO).isoformat()},
        "nba_player_watchlist": players,
        "candidate_counts": {
            "football": len(selected_football),
            "nba_games": len(nba[:max_nba]),
            "players": len(players)
        }
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="collector-output/fixtures.json")
    p.add_argument("--output", default="collector-feed.json")
    p.add_argument("--nba-next", help="Optional next Sarajevo calendar day football and NBA fixtures")
    a = p.parse_args()
    doc = json.loads(Path(a.input).read_text(encoding="utf-8"))
    next_nba=json.loads(Path(a.nba_next).read_text(encoding="utf-8")) if a.nba_next else None
    queue = build(doc, next_nba=next_nba)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(queue, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("CANDIDATE_QUEUE", json.dumps({"counts":queue["candidate_counts"],"source_status":queue["source_status"],"source_errors":len(queue["source_errors"])},ensure_ascii=False))
if __name__ == "__main__":
    main()
