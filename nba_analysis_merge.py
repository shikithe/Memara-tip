#!/usr/bin/env python3
"""Create an isolated NBA player-props analyst queue from ESPN rosters and bookmaker odds.

Never edits ESPN source, raw odds, football data, tickets or bankroll.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

def dt(value):
    if not value:
        raise ValueError("timestamp missing")
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)

def join(fixtures, props, now=None):
    now = now or datetime.now(timezone.utc)
    if fixtures.get("status") != "ok":
        raise ValueError("NBA fixture snapshot is not complete")
    collected = dt(fixtures["collected_at_utc"])
    if collected > now + timedelta(minutes=5) or now-collected > timedelta(hours=26):
        raise ValueError("NBA fixture snapshot is stale or future-dated")
    games = {str(g["event_id"]): g for g in fixtures.get("games", [])}
    players = {}
    for p in fixtures.get("players", []):
        key = (str(p["event_id"]), str(p["player_id"]))
        players.setdefault(key, []).append(p)
    generated = props.get("generated_at_utc")
    usable = False
    reason = "odds_not_yet_collected"
    if generated:
        try:
            odds_at = dt(generated)
            fixture_at = dt(props["fixture_snapshot_utc"])
            usable = (collected == fixture_at and
                      collected <= odds_at + timedelta(minutes=5) and
                      odds_at <= now + timedelta(minutes=5) and
                      now-odds_at <= timedelta(hours=3))
            reason = "ok" if usable else "odds_snapshot_not_current_fixture"
        except (ValueError, TypeError, KeyError):
            reason = "invalid_odds_timestamps"
    matched, rejected = [], {}
    seen = set()
    for offer in props.get("offers", []) if usable else []:
        try:
            event = str(offer["espn_event_id"])
            pid = str(offer["player_id"])
            group = players.get((event, pid), [])
            game = games.get(event)
            if not game or len(group) != 1:
                raise ValueError("missing_or_ambiguous_player_event")
            player = group[0]
            if (str(player["name"]).casefold() != str(offer["player"]).casefold() or
                str(player["team"]).casefold() != str(offer["team"]).casefold() or
                str(player["opponent"]).casefold() != str(offer["opponent"]).casefold()):
                raise ValueError("player_team_opponent_mismatch")
            start = dt(game["start_utc"])
            if abs((start-dt(offer["start_utc"])).total_seconds()) > 300:
                raise ValueError("event_start_mismatch")
            if not (now < start < now + timedelta(hours=26)):
                raise ValueError("event_not_upcoming")
            updated = dt(offer["last_update"])
            if updated > now + timedelta(minutes=5) or now-updated > timedelta(hours=3):
                raise ValueError("stale_bookmaker_odds")
            line = float(offer["points_line"])
            over, under = float(offer["over_odds"]), float(offer["under_odds"])
            if not (0 <= line <= 100 and 1 < over < 100 and 1 < under < 100):
                raise ValueError("invalid_line_or_price")
            book = str(offer.get("bookmaker_key") or offer.get("bookmaker") or "").strip()
            if not book:
                raise ValueError("missing_bookmaker_identity")
            key = (event, pid, book.casefold(), line)
            if key in seen:
                raise ValueError("duplicate_offer")
            seen.add(key)
            matched.append({
                "espn_event_id": event, "odds_event_id": offer.get("odds_event_id"),
                "start_utc": start.isoformat(), "player_id": pid,
                "player": player["name"], "team": player["team"],
                "opponent": player["opponent"],
                "participation": player.get("participation", "unverified"),
                "injury_status": player.get("injury_status", "unverified"),
                "market": "player_points", "points_line": line,
                "over_odds": over, "under_odds": under,
                "bookmaker_key": book, "last_update": updated.isoformat(),
                "source": offer.get("source", "the-odds-api.com"),
                "analysis_status": "pending",
                "publication_allowed": False
            })
        except (KeyError, ValueError, TypeError) as exc:
            reason_key = str(exc) if isinstance(exc, ValueError) else "malformed_offer"
            rejected[reason_key] = rejected.get(reason_key, 0) + 1
    matched.sort(key=lambda p: (p["start_utc"], p["player"], p["points_line"], p["bookmaker_key"]))
    return {
        "schema_version": "1.0", "generated_at_utc": now.isoformat(),
        "fixture_snapshot_utc": collected.isoformat(),
        "odds_snapshot_utc": generated if usable else None,
        "window_start_utc": fixtures.get("window_start_utc"),
        "window_end_utc": fixtures.get("window_end_utc"),
        "game_count": len(games), "player_candidate_count": len(fixtures.get("players", [])),
        "matched_offer_count": len(matched), "rejected_offer_counts": rejected,
        "odds_status": reason,
        "analysis_status": "ready" if matched else "awaiting_valid_odds",
        "publication_allowed": False, "offers": matched
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fixtures", default="collector-output/nba-next-24h.json")
    p.add_argument("--props", default="collector-output/nba-player-points.json")
    p.add_argument("--output", default="collector-output/nba-analysis-ready.json")
    a = p.parse_args()
    fixtures = json.loads(Path(a.fixtures).read_text(encoding="utf-8"))
    props = json.loads(Path(a.props).read_text(encoding="utf-8"))
    result = join(fixtures, props)
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("NBA_ANALYST_QUEUE", result["analysis_status"], result["matched_offer_count"],
          "offers", result["rejected_offer_counts"])

if __name__ == "__main__":
    main()
