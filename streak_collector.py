#!/usr/bin/env python3
"""Isolated Streak Breaker prototype. No writes to production files.

Input: JSON with fixtures containing completed historical games and upcoming
games. Only consecutive, completed matches count. Output is a JSON report.
No odds are invented, and no betting recommendations are automatically published.
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def analyze(fixtures, min_streak=5, limit=10):
    history = defaultdict(list)
    upcoming = defaultdict(list)
    for game in fixtures:
        home, away = game["home"], game["away"]
        if game.get("status") == "finished":
            hg, ag = game.get("home_goals"), game.get("away_goals")
            if not isinstance(hg, int) or not isinstance(ag, int) or min(hg, ag) < 0:
                continue
            for team in (home, away):
                history[team].append(game)
        elif game.get("status") == "scheduled":
            for team in (home, away):
                upcoming[team].append(game)
    result = []
    for team, matches in history.items():
        matches.sort(key=lambda g: g["kickoff"], reverse=True)
        streak = 0
        for match in matches:
            if match["home_goals"] + match["away_goals"] <= 2:
                streak += 1
            else:
                break
        if streak < min_streak or not upcoming[team]:
            continue
        nxt = min(upcoming[team], key=lambda g: g["kickoff"])
        result.append({
            "team": team, "league": nxt.get("league", "—"),
            "streak_length": streak,
            "opponent": nxt["away"] if nxt["home"] == team else nxt["home"],
            "kickoff": nxt["kickoff"],
            "pick": "3+ gola (kandidat, nije tip)",
            "odds": None, "status": "Čeka se analiza i provjera kvote"
        })
    result.sort(key=lambda x: (-x["streak_length"], x["kickoff"], x["team"]))
    return {"schema_version": 1, "updated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "test_only", "publication_allowed": False,
            "rule": "5+ consecutive completed matches with 0-2 total goals",
            "max_candidates": limit, "candidates": result[:limit]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    fixtures = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(fixtures, list):
        raise ValueError("Input must be a list of fixtures")
    output = analyze(fixtures)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Test-only streak candidates: {len(output['candidates'])}")


if __name__ == "__main__":
    main()
