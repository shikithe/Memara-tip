#!/usr/bin/env python3
"""Research-only mixed-sport C ticket selection. NEVER publishes or changes bankroll.

Inputs:
  collector-output/nba-analyst-research.json (NBA player markets)
  collector-output/ticket-c-match-markets.json (optional independently verified
    football 2+/3+ goals and basketball winner/total points markets)
A match-market record must contain: sport, market, event_id, selection, odds,
start_utc, odds_last_update, source, verified, analysis_verified, and
independent_event_check. Research-only NBA candidates remain excluded until
their publication checks are independently completed upstream.
"""
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("collector-output")
TARGET_ODDS = 10.0
MIN_LEGS = 3
ALLOWED_MATCH_MARKETS = {
    "football": {"goals_2_plus", "goals_3_plus"},
    "basketball": {"winner", "total_over", "total_under"},
}

def load(name):
    p = ROOT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def timestamp(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timezone required")
    return dt.astimezone(timezone.utc)

def valid_match(row, now):
    try:
        sport = str(row["sport"]).lower()
        market = str(row["market"]).lower()
        price = float(row["odds"])
        start = timestamp(row["start_utc"])
        updated = timestamp(row["odds_last_update"])
        if sport not in ALLOWED_MATCH_MARKETS or market not in ALLOWED_MATCH_MARKETS[sport]:
            return False, "unsupported_market"
        if not (math.isfinite(price) and price > 1.0):
            return False, "invalid_odds"
        if not now < start <= now + timedelta(hours=24):
            return False, "not_upcoming_24h"
        if not updated <= now + timedelta(minutes=5) and updated >= now - timedelta(hours=3):
            return False, "stale_or_future_odds"
        if not all(row.get(k) is True for k in ("verified", "analysis_verified", "independent_event_check")):
            return False, "unverified_match_analysis"
        if not row.get("source") or not row.get("event_id") or not row.get("selection"):
            return False, "missing_market_identity"
        if row.get("estimated_edge") is None or not math.isfinite(float(row["estimated_edge"])):
            return False, "missing_model_edge"
        return True, None
    except (ValueError, KeyError, TypeError, OverflowError):
        return False, "invalid_match_record"

def screen(now=None):
    now = now or datetime.now(timezone.utc)
    date = now.astimezone(ZoneInfo("Europe/Sarajevo")).date().isoformat()
    match_data = load("ticket-c-match-markets.json")
    analyst = load("nba-analyst-research.json")
    rows = match_data.get("candidates", [])
    eligible, rejected = [], {}
    def reject(reason):
        rejected[reason] = rejected.get(reason, 0) + 1

    for row in rows:
        ok, reason = valid_match(row, now)
        if not ok:
            reject(reason)
            continue
        eligible.append({
            "sport": row["sport"], "market": row["market"],
            "event_id": str(row["event_id"]), "selection": row["selection"],
            "odds": float(row["odds"]), "estimated_edge": float(row["estimated_edge"]),
            "source": row["source"], "start_utc": row["start_utc"],
            "odds_last_update": row["odds_last_update"],
        })

    for row in analyst.get("candidates", []):
        # The NBA analyst currently marks ALL outputs research_only.
        # Only a future independently validated candidate may pass this gate.
        if row.get("publication_allowed") is not True or row.get("data_gaps"):
            reject("nba_requires_independent_validation")
            continue
        try:
            start, updated = timestamp(row["start_utc"]), timestamp(row["odds_last_update"])
            price, edge = float(row["odds"]), float(row["estimated_edge"])
            if not (now < start <= now + timedelta(hours=24) and
                    now - timedelta(hours=3) <= updated <= now + timedelta(minutes=5) and
                    1.75 <= price <= 1.90 and math.isfinite(edge)):
                reject("nba_market_not_valid")
                continue
            eligible.append({
                "sport": "basketball", "market": "player_points_" + row["side"],
                "event_id": str(row["espn_event_id"]),
                "selection": row["player"] + " " + row["side"] + " " + str(row["line"]),
                "odds": price, "estimated_edge": edge,
                "source": row["bookmaker"], "start_utc": row["start_utc"],
                "odds_last_update": row["odds_last_update"],
            })
        except (KeyError, ValueError, TypeError):
            reject("nba_market_invalid")

    # Highest estimated edge first, no duplicate or conflicting event selections.
    eligible.sort(key=lambda r: (-r["estimated_edge"], -r["odds"], r["event_id"]))
    selected, seen_events, combined = [], set(), 1.0
    for row in eligible:
        if row["event_id"] in seen_events:
            reject("same_event_correlation_guard")
            continue
        selected.append(row)
        seen_events.add(row["event_id"])
        combined *= row["odds"]
        if len(selected) >= MIN_LEGS and combined >= TARGET_ODDS:
            break

    reached = len(selected) >= MIN_LEGS and combined >= TARGET_ODDS
    return {
        "date": date, "generated_at_utc": now.isoformat(),
        "state": "research_only", "publication_allowed": False,
        "target_odds": TARGET_ODDS, "minimum_legs": MIN_LEGS,
        "unlimited_legs": True, "target_reached": reached,
        "combined_odds": round(combined, 4) if selected else 0,
        "candidate_count": len(eligible), "selected_count": len(selected),
        "selected": selected if reached else [],
        "provisional_selection": selected,
        "rejected": rejected,
        "warnings": [
            "Research only; no ticket publication, bankroll changes or site writes",
            "Football and basketball match markets require a verified odds-and-analysis feed",
            "NBA player markets are blocked until independent context and bookmaker verification",
            "Ranking is by estimated edge; probability model calibration remains necessary",
        ],
    }

def main():
    result = screen()
    ROOT.mkdir(exist_ok=True)
    (ROOT / "ticket-c-research.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("C mixed research", result["candidate_count"], "eligible; target reached:", result["target_reached"])

if __name__ == "__main__":
    main()
