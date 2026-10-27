#!/usr/bin/env python3
"""NBA two-player test ticket builder. Never writes to MEMARA main or bank.

Input JSON: {"offers":[{"player":"...", "game":"...", "side":"OVER",
"line":24.5,"odds":1.85,"bookmaker":"...","source_url":"https://...",
"snapshot_utc":"...","start_utc":"...","status":"verified"}, ...]}
All fields must be explicitly provided; no market prices are fabricated.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def timestamp(s):
    value = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return value.astimezone(timezone.utc)


def build(data, now=None):
    now = now or datetime.now(timezone.utc)
    accepted, rejected = [], []
    for i, offer in enumerate(data.get("offers", [])):
        try:
            required = ("player", "game", "side", "line", "odds", "bookmaker",
                        "source_url", "snapshot_utc", "start_utc", "status")
            if any(k not in offer for k in required):
                raise ValueError("missing field")
            if offer["status"] != "verified":
                raise ValueError("unverified offer")
            if offer["side"] not in ("OVER", "UNDER"):
                raise ValueError("invalid side")
            if any(not isinstance(offer[k], str) or not offer[k].strip()
                   for k in ("player", "game", "bookmaker", "source_url")):
                raise ValueError("empty identity/source")
            if not offer["source_url"].startswith("https://"):
                raise ValueError("source must be HTTPS")
            line, odds = float(offer["line"]), float(offer["odds"])
            if not (math.isfinite(line) and math.isfinite(odds)
                    and line >= 0 and odds > 1):
                raise ValueError("invalid line/odds")
            if timestamp(offer["start_utc"]) <= now:
                raise ValueError("game already started")
            age = (now - timestamp(offer["snapshot_utc"])).total_seconds()
            if not -300 <= age <= 10800:
                raise ValueError("stale/future market snapshot")
            accepted.append(dict(offer, line=line, odds=odds))
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            rejected.append({"index": i, "reason": str(exc)})
    selected = []
    seen = set()
    for offer in accepted:
        if offer["player"].casefold() not in seen:
            selected.append(offer)
            seen.add(offer["player"].casefold())
        if len(selected) == 2:
            break
    return {"mode": "test_only", "publication_allowed": False,
            "bank_unchanged": True, "generated_at_utc": now.isoformat(),
            "status": "complete" if len(selected) == 2 else "insufficient_verified_offers",
            "ticket": selected,
            "combined_odds": round(math.prod(o["odds"] for o in selected), 3)
                             if len(selected) == 2 else None,
            "rejected": rejected,
            "warning": "Market verification flag is supplied by input provider; this script does not independently verify bookmakers, lineups, or injury news."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="collector-output/nba-ticket-test.json")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = build(data)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("NBA TEST:", result["status"], "players:", len(result["ticket"]),
          "combined odds:", result["combined_odds"])


if __name__ == "__main__":
    main()
