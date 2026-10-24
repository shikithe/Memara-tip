#!/usr/bin/env python3
"""MEMARA NBA 24-hour discovery (read-only, no ticket publication).

ESPN public feeds are unofficial and best-effort. A roster is NOT proof
that a player will participate. No lines/odds are invented.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Sarajevo")
ROOT = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

def get_json(url):
    req = Request(url, headers={"User-Agent": "MEMARA-NBA-Collector/1.0", "Accept": "application/json"})
    with urlopen(req, timeout=20) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("API response too large")
    return json.loads(raw)

def utc_date(value):
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timezone missing")
    return result.astimezone(timezone.utc)

def collect(now, hours=24):
    start = now.astimezone(timezone.utc)
    end = start + timedelta(hours=hours)
    # Date queries in UTC, not US local day, to avoid midnight cutoffs.
    day = start.date()
    dates = []
    while day <= end.date():
        dates.append(day.strftime("%Y%m%d"))
        day += timedelta(days=1)
    games, errors, seen = [], [], set()
    for day_str in dates:
        url = ROOT + "/scoreboard?" + urlencode({"dates": day_str, "limit": 500})
        try:
            events = get_json(url).get("events", [])
            if not isinstance(events, list):
                raise ValueError("events must be an array")
            for e in events:
                try:
                    timestamp = utc_date(e["date"])
                    if not start <= timestamp < end:
                        continue
                    if (e.get("status") or {}).get("type", {}).get("state") != "pre":
                        continue
                    event_id = str(e["id"])
                    if event_id in seen:
                        continue
                    competitors = e["competitions"][0]["competitors"]
                    teams = []
                    for side in ("home", "away"):
                        c = next(c for c in competitors if c["homeAway"] == side)
                        team = c["team"]
                        teams.append({"id": str(team["id"]), "name": team.get("displayName", team.get("name", "")), "home_away": side})
                    games.append({"event_id": event_id, "start_utc": timestamp.isoformat(), "start_sarajevo": timestamp.astimezone(TZ).isoformat(), "teams": teams})
                    seen.add(event_id)
                except (KeyError, ValueError, TypeError, StopIteration, IndexError) as exc:
                    errors.append(f"bad event: {exc}")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"scoreboard {day_str}: {type(exc).__name__}: {exc}")
    games.sort(key=lambda item: item["start_utc"])
    players, roster_cache = [], {}
    for game in games:
        for team in game["teams"]:
            tid = team["id"]
            if tid not in roster_cache:
                try:
                    data = get_json(ROOT + f"/teams/{tid}/roster")
                    athletes = data.get("athletes", [])
                    # ESPN sometimes groups athletes by position/category.
                    if isinstance(athletes, list):
                        flat = []
                        for item in athletes:
                            if isinstance(item, dict) and isinstance(item.get("items"), list):
                                flat.extend(item["items"])
                            else:
                                flat.append(item)
                        athletes = flat
                    roster_cache[tid] = athletes
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    errors.append(f"roster {tid}: {type(exc).__name__}: {exc}")
                    roster_cache[tid] = []
            opponent = next(x for x in game["teams"] if x["id"] != tid)
            for athlete in roster_cache[tid]:
                if not isinstance(athlete, dict):
                    continue
                player_id = athlete.get("id")
                name = athlete.get("displayName") or athlete.get("fullName")
                if not player_id or not name:
                    continue
                players.append({
                    "player_id": str(player_id), "name": name,
                    "team": team["name"], "opponent": opponent["name"],
                    "event_id": game["event_id"], "start_utc": game["start_utc"],
                    "participation": "unverified", "injury_status": "unverified",
                    "points_line": None, "over_odds": None, "under_odds": None,
                    "odds_source": None, "analysis_status": "pending"
                })
    return {
        "schema_version": "1.0", "source": "espn-public-unofficial",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "window_start_utc": start.isoformat(), "window_end_utc": end.isoformat(),
        "timezone_display": "Europe/Sarajevo", "games": games, "players": players,
        "game_count": len(games), "player_candidate_count": len(players),
        "limitations": ["Roster membership does not confirm game participation",
                         "No player prop odds or confirmed injuries are collected",
                         "No AI predictions or tickets are generated"],
        "status": "partial" if errors else "ok", "errors": errors,
        "publication_allowed": False
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=int, default=24)
    p.add_argument("--now-utc", help="Optional timezone-aware ISO datetime for reproducible tests")
    p.add_argument("--output", default="collector-output/nba-next-24h.json")
    args = p.parse_args()
    if not 1 <= args.hours <= 72:
        p.error("--hours must be between 1 and 72")
    now = utc_date(args.now_utc) if args.now_utc else datetime.now(timezone.utc)
    result = collect(now, args.hours)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {result['game_count']} games, {result['player_candidate_count']} player candidates, {len(result['errors'])} errors")
    return 2 if result["errors"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
