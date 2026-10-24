#!/usr/bin/env python3
"""Research-only free NBA player history using available odds-offer ESPN athlete IDs.

Dynamic daily player pool, deduplicated by athlete ID. Reads published odds
snapshot to discover targets, never uses a hand-curated 12-player watchlist.
Stores merged observed games with event IDs; avoids duplicate boxscores.
ESPN public endpoints are unofficial and may change. No predictions generated.
"""
import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"


def fetch(url):
    with urlopen(Request(url, headers={"Accept": "application/json",
            "User-Agent": "MemaraSix-Research/1.1"}), timeout=20) as response:
        return json.load(response)


def targets_from_offers(path, now):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(payload["generated_at_utc"].replace("Z", "+00:00"))
        if generated.tzinfo is None or abs((now - generated).total_seconds()) > 36 * 3600:
            return {}, "stale_odds"
    except (OSError, ValueError, KeyError, TypeError):
        return {}, "odds_missing"
    targets = {}
    for offer in payload.get("offers", []):
        player_id = str(offer.get("player_id") or "").strip()
        name = str(offer.get("player") or "").strip()
        if player_id.isdigit() and name and offer.get("points_line") is not None:
            if player_id in targets and targets[player_id] != name:
                continue
            targets[player_id] = name
    return targets, ("ok" if targets else "no_offers")


def parse_game(summary, event, day):
    rows = []
    for group in (summary.get("boxscore") or {}).get("players", []):
        team = (group.get("team") or {}).get("displayName")
        for section in group.get("statistics", []):
            keys = [str(x).lower() for x in section.get("keys", [])]
            labels = [str(x).lower() for x in section.get("labels", [])]
            pts_idx = next((i for i, x in enumerate(keys) if x in ("points", "pts")), None)
            if pts_idx is None:
                pts_idx = next((i for i, x in enumerate(labels) if x in ("points", "pts")), None)
            min_idx = next((i for i, x in enumerate(keys) if x in ("minutes", "min")), None)
            if min_idx is None:
                min_idx = next((i for i, x in enumerate(labels) if x == "min"), None)
            for item in section.get("athletes", []):
                athlete = item.get("athlete") or {}
                values = item.get("stats") or []
                try:
                    points = int(float(values[pts_idx]))
                    minutes = str(values[min_idx]) if min_idx is not None else None
                except (IndexError, ValueError, TypeError):
                    continue
                if not athlete.get("id") or not athlete.get("displayName"):
                    continue
                rows.append({"player_id": str(athlete["id"]), "player": athlete["displayName"],
                    "team": team, "points": points, "minutes": minutes,
                    "game_id": str(event), "game_date": day})
    return rows


def run(days, max_summaries, offers_path, history_path, now=None):
    now = now or datetime.now(timezone.utc)
    targets, source_status = targets_from_offers(offers_path, now)
    result = {"date_utc": now.date().isoformat(), "generated_at_utc": now.isoformat(),
        "provider": "espn-public-unofficial", "no_api_key_required": True,
        "target_source": "the-odds-api-player-points", "target_status": source_status,
        "target_player_count": len(targets), "statistics_not_predictions": True,
        "limitations": "Unofficial incomplete past boxscores. No independent player projection, injury check or odds-value claim.",
        "status": "ok" if targets else "no_fresh_target_offers",
        "requested_summaries": 0, "errors": [], "players": []}
    # Preserve prior genuinely observed games, but never treat previous daily average as raw history.
    cached = {}
    try:
        old = json.loads(Path(history_path).read_text(encoding="utf-8"))
        if old.get("provider") == "espn-public-unofficial":
            for player in old.get("players", []):
                pid = str(player.get("player_id", ""))
                if not pid.isdigit():
                    continue
                for row in player.get("recent_games", []):
                    if str(row.get("player_id", "")) == pid and str(row.get("game_id", "")).isdigit() \
                            and isinstance(row.get("points"), int):
                        cached.setdefault(pid, {})[str(row["game_id"])] = row
    except (OSError, ValueError, TypeError, KeyError):
        pass
    if not targets:
        # Avoid overwriting existing useful history on days without current props.
        result["players_with_stats"] = 0
        return result
    events = []
    for age in range(1, days + 1):
        day = (now - timedelta(days=age)).strftime("%Y%m%d")
        try:
            doc = fetch(BASE + "/scoreboard?dates=" + day)
            for event in doc.get("events", []):
                status = ((event.get("status") or {}).get("type") or {}).get("state")
                if status == "post" and str(event.get("id", "")).isdigit():
                    events.append((str(event["id"]), day))
        except (HTTPError, URLError, ValueError, TypeError):
            result["errors"].append("Scoreboard unavailable for " + day)
    seen_events = set()
    unique_events = []
    for eid, day in events:
        if eid not in seen_events:
            seen_events.add(eid)
            unique_events.append((eid, day))
    # Missing players preferentially gain older history; all results include all athletes per boxscore.
    unique_events = unique_events[:max_summaries]
    for eid, day in unique_events:
        # Skip event if its relevant athletes already have this event; there is no way to
        # know the participants pre-fetch, so cache deduplication happens after response.
        try:
            summary = fetch(BASE + "/summary?event=" + eid)
            result["requested_summaries"] += 1
            for row in parse_game(summary, eid, day):
                pid = row["player_id"]
                if pid in targets:
                    cached.setdefault(pid, {})[eid] = row
        except (HTTPError, URLError, ValueError, TypeError):
            result["errors"].append("Boxscore unavailable for event " + eid)
        time.sleep(.15)
    for pid, name in sorted(targets.items(), key=lambda kv: kv[1]):
        games = sorted(cached.get(pid, {}).values(), key=lambda row: (row.get("game_date", ""), row["game_id"]), reverse=True)[:20]
        result["players"].append({"player_id": pid, "player": name, "recent_games": games,
            "games_found": len(games),
            "average_points": round(sum(g["points"] for g in games) / len(games), 2) if games else None,
            "status": "historical_sample" if games else "insufficient_coverage",
            "sample_sufficient_for_model": False, "not_a_projection": True})
    result["players_with_stats"] = sum(p["games_found"] > 0 for p in result["players"])
    if result["errors"] and not result["requested_summaries"]:
        result["status"] = "source_unavailable"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--max-summaries", type=int, default=40)
    parser.add_argument("--offers", default="collector-output/nba-player-points.json")
    parser.add_argument("--output", default="collector-output/nba-free-statistics.json")
    args = parser.parse_args()
    if not 1 <= args.days <= 21 or not 1 <= args.max_summaries <= 60:
        parser.error("Invalid bounded sampling controls")
    result = run(args.days, args.max_summaries, args.offers, args.output)
    path = Path(args.output)
    if result["target_status"] != "ok" and path.exists():
        print("NBA_FREE_STATS: odds unavailable/stale; preserving prior history")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("NBA_FREE_STATS", json.dumps({"status": result["status"],
        "targets": result["target_player_count"], "players_with_stats": result["players_with_stats"],
        "boxscores": result["requested_summaries"], "errors": len(result["errors"])}))


if __name__ == "__main__":
    main()
