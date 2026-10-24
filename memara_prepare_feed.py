#!/usr/bin/env python3
"""Prepare a read-only MEMARASIX analyst queue from collector JSON.

Does not predict, select bet legs, fetch odds, modify the bank or publish tickets.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

def build(data, max_football=30, max_nba=12):
    fixtures = data.get("fixtures", [])
    if not isinstance(fixtures, list):
        raise ValueError("fixtures must be an array")
    football = [f for f in fixtures if f.get("sport") == "football" and f.get("status") == "pre"]
    nba = [f for f in fixtures if f.get("sport") == "basketball" and f.get("league") == "nba" and f.get("status") == "pre"]
    football.sort(key=lambda f: (0 if f.get("provider") == "thesportsdb-free-limited" else 1, f.get("start_utc", "")))
    nba.sort(key=lambda f: f.get("start_utc", ""))
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
        "football_candidates": football[:max_football],
        "nba_games": nba[:max_nba],
        "nba_player_watchlist": players,
        "candidate_counts": {
            "football": len(football[:max_football]),
            "nba_games": len(nba[:max_nba]),
            "players": len(players)
        }
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="collector-output/fixtures.json")
    p.add_argument("--output", default="collector-feed.json")
    a = p.parse_args()
    doc = json.loads(Path(a.input).read_text(encoding="utf-8"))
    queue = build(doc)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(queue, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("CANDIDATE_QUEUE", json.dumps({"counts":queue["candidate_counts"],"source_status":queue["source_status"],"source_errors":len(queue["source_errors"])},ensure_ascii=False))
if __name__ == "__main__":
    main()
