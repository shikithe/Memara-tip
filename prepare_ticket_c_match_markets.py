#!/usr/bin/env python3
"""Prepare football and basketball match markets from a verified odds snapshot.
Research only: does not place bets, publish tickets, or modify bankroll.
Input: collector-output/match-odds-snapshot.json
"""
import json
from pathlib import Path

ROOT = Path("collector-output")
MARKETS = {"football": {"goals_2_plus", "goals_3_plus"},
           "basketball": {"winner", "total_over", "total_under"}}

def prepare(snapshot):
    result = []
    for row in snapshot.get("offers", []):
        if row.get("market") not in MARKETS.get(row.get("sport"), set()):
            continue
        try:
            price = float(row["odds"])
            if not 1 < price < 1000:
                continue
            result.append({
                "sport": row["sport"], "market": row["market"],
                "event_id": row["event_id"], "selection": row["selection"],
                "odds": price, "start_utc": row["start_utc"],
                "odds_last_update": row["odds_last_update"],
                "source": row["source"],
                "verified": bool(row.get("verified", False)),
                "analysis_verified": bool(row.get("analysis_verified", False)),
                "independent_event_check": bool(row.get("independent_event_check", False)),
                "estimated_edge": row.get("estimated_edge"),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return {"state": "research_only", "publication_allowed": False,
            "count": len(result), "candidates": result}

if __name__ == "__main__":
    source = ROOT / "match-odds-snapshot.json"
    data = json.loads(source.read_text()) if source.exists() else {}
    ROOT.mkdir(exist_ok=True)
    (ROOT / "ticket-c-match-markets.json").write_text(
        json.dumps(prepare(data), ensure_ascii=False, indent=2) + "\n")
    print("Prepared match markets:", len(prepare(data)["candidates"]))
