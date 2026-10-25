#!/usr/bin/env python3
"""Enrich MemaraSix analyst queue with verified-source NBA player points snapshots.

Never touches published tickets or bank. Only attach bookmaker offers if
fixtures and odds match exact ESPN event ID and scheduled start, and the
market snapshot is fresh. Odds may not be offered in Bosnia and Herzegovina.
"""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SAR = ZoneInfo("Europe/Sarajevo")

def parse_time(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)

def enrich(feed, props, now=None):
    now = now or datetime.now(timezone.utc)
    result = dict(feed)
    result["nba_player_points_offers"] = []
    result["nba_prop_status"] = "unavailable"
    result["nba_prop_note"] = "Source bookmaker odds only; not necessarily available at Mozzartbet BiH. Independent AI assessment needed."
    if feed.get("date") != now.astimezone(SAR).date().isoformat():
        result["nba_prop_note"] = "Collector feed date is not today; no odds merged."
        return result
    try:
        snapshot = parse_time(props["generated_at_utc"])
    except (KeyError, ValueError, TypeError):
        result["nba_prop_note"] = "Invalid odds snapshot timestamp."
        return result
    if snapshot > now + timedelta(minutes=5) or now - snapshot > timedelta(hours=3):
        result["nba_prop_note"] = "Odds snapshot too old or from the future; no odds merged."
        return result
    events = {}
    for game in feed.get("nba_games", []):
        if game.get("sport") != "basketball" or game.get("league") != "nba" or game.get("status") != "pre":
            continue
        event_id = str(game.get("id", "")).split(":")[-1]
        try:
            start = parse_time(game["start_utc"])
        except (ValueError, TypeError, KeyError):
            continue
        if start > now and start < now + timedelta(hours=42):
            events[event_id] = start
    seen = set()
    rejected_players = 0
    for offer in props.get("offers", []):
        if not isinstance(offer, dict):
            continue
        event_id = str(offer.get("espn_event_id", ""))
        start = events.get(event_id)
        if start is None:
            continue
        try:
            odds_start = parse_time(offer["start_utc"])
            updated = parse_time(offer["last_update"])
            line = float(offer["points_line"])
            over = float(offer["over_odds"])
            under = float(offer["under_odds"])
        except (KeyError, TypeError, ValueError):
            continue
        if abs((odds_start-start).total_seconds()) > 300:
            continue
        if updated > now + timedelta(minutes=5) or now-updated > timedelta(hours=3):
            continue
        if line < 0 or over <= 1 or under <= 1:
            continue
        player = str(offer.get("player", "")).strip()
        bookmaker = str(offer.get("bookmaker", "")).strip()
        player_id = str(offer.get("player_id", "")).strip()
        if not all((player, bookmaker, player_id)):
            continue
        expected = props.get('verified_player_teams', {}).get(player_id)
        if expected and str(expected).casefold() != str(offer.get('team', '')).casefold():
            rejected_players += 1
            continue
        key = (event_id, player_id, bookmaker.casefold(), line)
        if key in seen:
            continue
        seen.add(key)
        result["nba_player_points_offers"].append({
            "player_id": player_id,
            "player": player,
            "team": offer.get("team"),
            "opponent": offer.get("opponent"),
            "espn_event_id": event_id,
            "start_utc": start.isoformat().replace("+00:00", "Z"),
            "points_line": line,
            "over_odds": over,
            "under_odds": under,
            "bookmaker": bookmaker,
            "bookmaker_key": offer.get("bookmaker_key"),
            "last_update": updated.isoformat().replace("+00:00", "Z"),
            "source": "the-odds-api.com",
            "analysis_status": "unanalysed",
            "mozart_bih_verified": False
        })
    result["nba_player_points_offers"].sort(key=lambda x: (x["start_utc"], x["player"], x["bookmaker"], x["points_line"]))
    result["nba_prop_rejected_team_mismatch"] = rejected_players
    result["nba_prop_count"] = len(result["nba_player_points_offers"])
    result["nba_prop_status"] = "available_for_analysis" if result["nba_prop_count"] else "no_verified_matches"
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--feed", default="collector-feed.json")
    p.add_argument("--props", default="collector-output/nba-player-points.json")
    p.add_argument("--output", default="collector-feed.json")
    a = p.parse_args()
    feed = json.loads(Path(a.feed).read_text(encoding="utf-8"))
    props = json.loads(Path(a.props).read_text(encoding="utf-8"))
    result = enrich(feed, props)
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("NBA_PROP_ENRICH", json.dumps({"status":result["nba_prop_status"],"offers":result.get("nba_prop_count",0),"feed_date":result.get("date")}))
if __name__ == "__main__":
    main()
