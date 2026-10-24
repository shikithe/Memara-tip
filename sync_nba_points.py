#!/usr/bin/env python3
"""Sync NBA player-points offers into a separate JSON file (no ticket edits).
Requires GitHub secret THE_ODDS_API_KEY. Provider: the-odds-api.com v4.
"""
import json, os, sys, argparse, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://api.the-odds-api.com/v4/sports/basketball_nba"

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.lower().replace(".", "").replace("-", " ").split())

def fetch(url, key):
    # API key via header; no credentials in URLs, logs or repository files.
    req = Request(url, headers={"x-api-key": key, "Accept": "application/json",
                                "User-Agent": "MEMARA-NBA-Props/1.0"})
    with urlopen(req, timeout=25) as r:
        return json.load(r)

def run(source, key, region):
    with open(source, encoding="utf-8") as f:
        collected = json.load(f)
    if collected.get("status") != "ok":
        raise RuntimeError("Fixture data incomplete; refusing to publish props")
    games = collected.get("games", [])
    players = collected.get("players", [])
    by_game = {}
    for player in players:
        by_game.setdefault(player["event_id"], []).append(player)
    events = fetch(BASE + "/events?" + urlencode({"apiKey": key}), key)
    offers, unmatched, errors = [], [], []
    for game in games:
        candidates = [e for e in events if
                      {norm(e.get("home_team", "")), norm(e.get("away_team", ""))}
                      == {norm(t["name"]) for t in game["teams"]} and
                      abs((datetime.fromisoformat(e["commence_time"].replace("Z","+00:00")) -
                           datetime.fromisoformat(game["start_utc"])).total_seconds()) < 3600]
        if len(candidates) != 1:
            unmatched.append({"game": game["event_id"], "reason": "event match not unique"})
            continue
        eid = candidates[0]["id"]
        query = urlencode({"apiKey": key, "regions": region, "markets": "player_points", "oddsFormat": "decimal"})
        try:
            payload = fetch(BASE + f"/events/{eid}/odds?" + query, key)
        except (HTTPError, URLError, ValueError) as exc:
            errors.append(f"Could not load props for game {game['event_id']}: {type(exc).__name__}")
            continue
        matching = {}
        for player in by_game.get(game["event_id"], []):
            matching.setdefault(norm(player["name"]), []).append(player)
        for book in payload.get("bookmakers", []):
            for market in book.get("markets", []):
                if market.get("key") != "player_points": continue
                paired = {}
                for outcome in market.get("outcomes", []):
                    player_name = outcome.get("description")
                    side = str(outcome.get("name", "")).lower()
                    line = outcome.get("point")
                    price = outcome.get("price")
                    if side not in ("over", "under") or not player_name or not isinstance(line, (float, int)) or not isinstance(price, (float, int)):
                        continue
                    keypair = (norm(player_name), float(line))
                    paired.setdefault(keypair, {})[side] = float(price)
                for (name, line), odds in paired.items():
                    choices = matching.get(name, [])
                    if len(choices) != 1 or not {"over", "under"} <= set(odds):
                        continue
                    player = choices[0]
                    offers.append({"player_id": player["player_id"], "player": player["name"],
                        "team": player["team"], "opponent": player["opponent"],
                        "espn_event_id": game["event_id"], "odds_event_id": eid,
                        "start_utc": game["start_utc"], "points_line": line,
                        "over_odds": odds["over"], "under_odds": odds["under"],
                        "bookmaker": book.get("title"), "bookmaker_key": book.get("key"),
                        "last_update": market.get("last_update") or book.get("last_update"),
                        "source": "the-odds-api.com", "status": "unanalysed"})
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "fixture_snapshot_utc": collected.get("collected_at_utc"),
            "region": region, "offer_count": len(offers), "offers": offers,
            "unmatched_games": unmatched, "errors": errors,
            "publication_allowed": False, "analysis_status": "not_run"}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="collector-output/nba-next-24h.json")
    p.add_argument("--output", default="collector-output/nba-player-points.json")
    p.add_argument("--region", choices=("us","uk","eu","au"), default="us")
    a = p.parse_args()
    secret = os.environ.get("THE_ODDS_API_KEY")
    if not secret:
        p.error("THE_ODDS_API_KEY missing; add as a GitHub Actions secret")
    try:
        result = run(a.input, secret, a.region)
    except (OSError, ValueError, RuntimeError, HTTPError, URLError) as e:
        print(f"SYNC FAILED: {type(e).__name__} (check source and API access)", file=sys.stderr)
        return 1
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Matched player points offers:", result["offer_count"],
          "unmatched games:", len(result["unmatched_games"]),
          "request errors:", len(result["errors"]))
    return 2 if result["errors"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
