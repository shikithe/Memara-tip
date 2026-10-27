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
    """Detect 0–2, 3+, home-win (1), and home-team 2+ scoring streaks.

    '1' and 'tim1_2plus' use home fixtures only; 0–2 and 3+ use
    the team's fixtures at either venue. The next fixture must be at home
    for home-only markets. Home-team 2+ requires only two consecutive\n    home appearances; away games do not interrupt that home-only sequence.\n    Streaks describe history, not betting signals.
    """
    history = defaultdict(list)
    upcoming = defaultdict(list)
    for game in fixtures:
        home, away = game["home"], game["away"]
        if game.get("status") == "finished":
            hg, ag = game.get("home_goals"), game.get("away_goals")
            if (type(hg) is not int or type(ag) is not int
                    or min(hg, ag) < 0):
                continue
            for team in (home, away):
                history[team].append(game)
        elif game.get("status") == "scheduled":
            for team in (home, away):
                upcoming[team].append(game)

    rules = [
        ("0-2", "0–2 gola", lambda g: g["home_goals"] + g["away_goals"] <= 2, False),
        ("3plus", "3+ gola", lambda g: g["home_goals"] + g["away_goals"] >= 3, False),
        ("1", "Tip 1 (pobjeda domaćina)", lambda g: g["home_goals"] > g["away_goals"], True),
        ("tim1_2plus", "Tim 1 daje 2+ gola", lambda g: g["home_goals"] >= 2, True),
    ]
    result = []
    for team, matches in history.items():
        if not upcoming[team]:
            continue
        nxt = min(upcoming[team], key=lambda g: g["kickoff"])
        for key, label, predicate, home_only in rules:
            if home_only and nxt["home"] != team:
                continue
            sample = [g for g in matches if not home_only or g["home"] == team]
            sample.sort(key=lambda g: g["kickoff"], reverse=True)
            streak = 0
            for match in sample:
                if predicate(match):
                    streak += 1
                else:
                    break
            required_streak = 2 if key == "tim1_2plus" else min_streak
            if streak < required_streak:
                continue
            result.append({
                "team": team, "league": nxt.get("league", "—"),
                "streak_type": key, "streak_label": label,
                "streak_length": streak, "sample_scope": "home" if home_only else "all",
                "opponent": nxt["away"] if nxt["home"] == team else nxt["home"],
                "kickoff": nxt["kickoff"],
                "pick": "Kandidat za analizu prekida: " + label,
                "odds": None, "status": "Čeka se analiza i provjera kvote"
            })
    result.sort(key=lambda x: (-x["streak_length"], x["kickoff"], x["team"], x["streak_type"]))
    return {"schema_version": 2, "updated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "test_only", "publication_allowed": False,
            "rules": ["0-2", "3plus", "1", "tim1_2plus"],
            "min_streak": min_streak, "min_streak_by_type": {"tim1_2plus": 2}, "max_candidates": limit,
            "candidates": result[:limit]}


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
