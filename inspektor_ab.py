#!/usr/bin/env python3
"""Senzor A/B -> Inspektor: resume from first missing confirmed stage.

Never approve or invent tickets. Does not restart valid completed upstream stages.
Uses the published same-day MemaraSix data and current ListaSix shared artifacts.
"""
import argparse
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from check_ab_publication import check

TZ = ZoneInfo("Europe/Sarajevo")
BASE = "https://raw.githubusercontent.com/shikithe/Slavojka/main/"
ODDS = ("home_odds", "draw_odds", "away_odds", "over25_odds", "btts_yes_odds", "btts_no_odds")

def valid_odd(n):
    return isinstance(n, (int, float)) and not isinstance(n, bool) and 1.01 < n < 50

def inspect(site, feed, active, scout, today, history=None, top10=None):
    tickets = check(site, today)
    result = {"date": today, "tickets": tickets, "next_stage": None, "reason": "", "ready": {}}
    if tickets["both_published"]:
        result.update(next_stage="complete", reason="A and B published: sensor stops for today")
        return result
    if not isinstance(feed, dict) or feed.get("date") != today or not feed.get("football_candidates"):
        result.update(next_stage="espn", reason="Fresh nonempty ESPN list missing")
        return result
    rows = feed["football_candidates"]
    ids = {f.get("fixture_id") for f in rows}
    if len(ids) != len(rows) or None in ids:
        result.update(next_stage="espn", reason="Invalid or duplicate ESPN IDs")
        return result
    result["ready"]["espn"] = len(rows)
    if not isinstance(active, dict) or active.get("date") != today or not isinstance(active.get("fixtures"), list):
        result.update(next_stage="tipsterarea", reason="Today TipsterArea odds list missing")
        return result
    byid = {f.get("fixture_id"): f for f in active["fixtures"]}
    if len(byid) != len(active["fixtures"]) or set(byid) != ids:
        result.update(next_stage="tipsterarea", reason="Odds list not 1:1 with today's ESPN fixtures")
        return result
    missing = []
    for fixture in rows:
        row = byid[fixture["fixture_id"]]
        if row.get("datetime") != fixture.get("start_utc") or row.get("match") != fixture.get("home") + " - " + fixture.get("away"):
            result.update(next_stage="tipsterarea", reason="ESPN/odds fixture identity mismatch")
            return result
        if not any(valid_odd(row.get(field)) for field in ODDS):
            missing.append(fixture["fixture_id"])
    result["ready"]["tipsterarea_quoted"] = len(rows) - len(missing)
    result["missing_odds_ids"] = missing
    if (
        not isinstance(history, dict) or history.get("date") != today or
        {x.get("fixture_id") for x in history.get("fixtures", [])} != ids
    ):
        result.update(next_stage="history", reason="Today's ESPN last-five/H2H history missing or stale")
        return result
    # The existing fallback Scout is allowed to operate with partial prices.
    # Flag missing quote recovery separately; never report false completeness.
    if missing:
        result["ai_quote_recovery_needed"] = True
    if not isinstance(scout, dict) or scout.get("date") != today or scout.get("source_feed_generated_at_utc") != feed.get("generated_at_utc") or scout.get("all_fixtures_evaluated") != len(rows):
        result.update(next_stage="scout_6of6", reason="Scout 6/6 report absent, stale or incomplete")
        return result
    result["ready"]["scout_6of6"] = True
    # TOP10_READY is the terminal preparation checkpoint. Verify today's
    # actual handoff and matching ESPN IDs, not merely a stale named flag.
    handoff = scout.get("detailed_ai_handoff", {})
    candidates = top10.get("candidates", []) if isinstance(top10, dict) else []
    ids_top10 = top10.get("fixture_ids", []) if isinstance(top10, dict) else []
    valid_top10 = (
        isinstance(top10, dict) and top10.get("date") == today
        and top10.get("feedback") == "TOP10_READY"
        and isinstance(top10.get("source_fingerprint"), str)
        and len(top10["source_fingerprint"]) == 64
        and isinstance(candidates, list) and bool(candidates)
        and top10.get("count") == len(candidates)
        and isinstance(ids_top10, list)
        and ids_top10 == [x.get("fixture_id") for x in candidates if isinstance(x, dict)]
        and len(set(ids_top10)) == len(ids_top10)
        and set(ids_top10).issubset(ids)
        and handoff.get("count") == len(candidates)
        and [x.get("fixture_id") for x in handoff.get("candidates", [])] == ids_top10
    )
    if valid_top10:
        result.update(
            next_stage="await_publication",
            feedback="TOP10_CONFIRMED_WAIT_PUBLICATION",
            source_fingerprint=top10["source_fingerprint"],
            top10_count=len(candidates),
            reason="TOP10_READY confirmed; stop technical inspections until 13:00 Sarajevo",
        )
        return result
    result.update(next_stage="ai_analysis", reason="Scout exists; TOP10_READY not yet confirmed")
    return result

def remote_json(name):
    try:
        req = urllib.request.Request(BASE + name, headers={"User-Agent": "MemaraSix-Inspector/1.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status != 200:
                return None
            return json.load(response)
    except (OSError, ValueError, json.JSONDecodeError):
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="collector-output/ab-inspector.json")
    parser.add_argument("--date", default=datetime.now(TZ).date().isoformat())
    parser.add_argument("--offline-dir", help="Optional test fixtures directory replacing remote ListaSix")
    args = parser.parse_args()
    site = json.loads(Path("data.json").read_text(encoding="utf-8"))
    if args.offline_dir:
        root = Path(args.offline_dir)
        def load(name):
            p = root / name
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    else:
        load = remote_json
    result = inspect(site, load("shared/collector-feed.json"), load("shared/active-list.json"),
                     load("shared/agent/scout-six-markets.json"), args.date,
                     load("shared/agent/history-h2h.json"),
                     load("shared/agent/top10-feedback.json"))
    result["checked_at_sarajevo"] = datetime.now(TZ).isoformat()
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as out:
            out.write("next_stage=" + result["next_stage"] + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
