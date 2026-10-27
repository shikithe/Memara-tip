#!/usr/bin/env python3
"""Independent ESPN history adapter for Streak Breaker test branch.

Reads the league list from MEMARA collector.py, but never imports its main()
or writes to any MEMARA production file. ESPN is unofficial/best-effort.
"""
import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from collector import FOOTBALL, ROOT


def convert(event, league):
    try:
        comp = event["competitions"][0]
        competitors = comp["competitors"]
        home = next(x for x in competitors if x["homeAway"] == "home")
        away = next(x for x in competitors if x["homeAway"] == "away")
        state = event["status"]["type"]["state"]
        kickoff = event.get("date") or comp["date"]
        start = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        if start.tzinfo is None:
            return None
        row = {
            "id": f"espn:football:{league}:{event['id']}",
            "league": league,
            "home": home["team"]["displayName"],
            "away": away["team"]["displayName"],
            "kickoff": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if state == "post" and event["status"]["type"].get("completed") is True:
            row.update(status="finished", home_goals=int(home["score"]),
                       away_goals=int(away["score"]))
        elif state == "pre":
            row["status"] = "scheduled"
        else:
            return None
        return row
    except (KeyError, TypeError, ValueError, IndexError, StopIteration, AttributeError):
        return None


def fetch_history(today, days_back, days_ahead, leagues):
    rows, errors, seen = [], [], set()
    for league in leagues:
        for offset in range(-days_back, days_ahead + 1):
            day = today + timedelta(days=offset)
            url = f"{ROOT}/soccer/{league}/scoreboard?" + urlencode({
                "dates": day.strftime("%Y%m%d"), "limit": 500
            })
            try:
                request = Request(url, headers={
                    "User-Agent": "MEMARA-Streak-Test/1.0",
                    "Accept": "application/json"
                })
                with urlopen(request, timeout=15) as response:
                    raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise ValueError("Response exceeds 8MB")
                events = json.loads(raw)["events"]
                for event in events:
                    row = convert(event, league)
                    if row and row["id"] not in seen:
                        rows.append(row)
                        seen.add(row["id"])
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(f"{league} {day}: {type(exc).__name__}: {exc}")
    return sorted(rows, key=lambda x: x["kickoff"]), errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--days-back", type=int, default=70)
    parser.add_argument("--days-ahead", type=int, default=7)
    parser.add_argument("--league", action="append")
    parser.add_argument("--output", default="collector-output/streak-history-test.json")
    args = parser.parse_args()
    if not (0 <= args.days_back <= 120 and 0 <= args.days_ahead <= 14):
        parser.error("days-back must be 0..120 and days-ahead 0..14")
    target = date.fromisoformat(args.date)
    rows, errors = fetch_history(target, args.days_back, args.days_ahead,
                                 args.league or FOOTBALL)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(rows)} fixture records; {len(errors)} source errors")
    for error in errors[:15]:
        print("SOURCE WARNING:", error)
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
