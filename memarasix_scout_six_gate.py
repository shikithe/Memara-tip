#!/usr/bin/env python3
"""Mandatory full Scout 6/6 check for NEW AI-approved football A/B tickets.

Never selects tickets or changes balances. The NBA-only C flow is unchanged.
Checks all six pre-match probability estimates for EVERY ESPN match and
enforces exactly the strongest modeled market per selected fixture.
Scout report must cryptographically match the synchronized ListaSix offer
and history. All percentages are model estimates, NOT proven/calibrated.
"""
import base64
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from memarasix_sync_listasix import canonical_hash

SOURCE_URL = ("https://api.github.com/repos/shikithe/Slavojka/"
              "contents/shared/agent/scout-six-markets.json?ref=main")
MARKETS = ("1", "X", "2", "3+", "GG", "NG")
FIELDS = {"1": "home_odds", "X": "draw_odds", "2": "away_odds",
          "3+": "over25_odds", "GG": "btts_yes_odds", "NG": "btts_no_odds"}

def fetch_report(url=SOURCE_URL):
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MemaraSix-Scout-6of6-validation",
        "Cache-Control": "no-cache",
    })
    with urlopen(request, timeout=35) as response:
        response_json = json.loads(response.read(20_000_000))
    if response_json.get("encoding") != "base64":
        raise ValueError("Missing canonical Scout report content")
    return json.loads(base64.b64decode(response_json["content"]))

def validate_scout(approval, active, history, receipt, scout):
    """Validate entire score matrix, all six markets, and exact top pick."""
    tickets = [t for t in approval.get("tickets", [])
               if isinstance(t, dict) and t.get("id") in ("A", "B")]
    if not tickets:
        return {"checked": False, "reason": "NBA-only C requires no football Scout"}

    today = approval.get("date")
    if not today or any(d.get("date") != today for d in (active, history, receipt, scout)):
        raise ValueError("Scout 6/6 not current for this AI approval")
    if scout.get("source_active_sha256") != receipt.get("active_sha256"):
        raise ValueError("Scout was not calculated against the synchronized active list")
    if scout.get("source_active_sha256") != canonical_hash(active):
        raise ValueError("Scout references a different active-list snapshot")
    if scout.get("source_history_sha256") != canonical_hash(history):
        raise ValueError("Scout was not calculated against the synchronized history")
    fixtures = active.get("fixtures", [])
    expected_ids = {x.get("fixture_id") for x in fixtures}
    if not expected_ids or len(expected_ids) != len(fixtures):
        raise ValueError("Duplicate/missing ESPN match identity in approved snapshot")
    rows = scout.get("ranked_fixtures", [])
    if not isinstance(rows, list) or len(rows) != len(expected_ids):
        raise ValueError("Scout must evaluate EVERY ESPN match, not a selected shortlist")
    if scout.get("total_espn_fixtures") != len(expected_ids):
        raise ValueError("Scout match count does not equal ESPN source")
    if scout.get("total_market_probabilities") != len(expected_ids) * 6:
        raise ValueError("Scout has not evaluated six markets per match")
    ranked = {}
    for row in rows:
        fid = row.get("fixture_id")
        if not fid or fid in ranked or fid not in expected_ids:
            raise ValueError("Scout contains an unknown/duplicated match")
        p = row.get("probability_pct")
        if not isinstance(p, dict) or set(p.keys()) != set(MARKETS):
            raise ValueError("Scout probability matrix lacks one or more of six markets")
        for market in MARKETS:
            value = p[market]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError("Invalid percentage for " + str(fid))
        if abs(sum(p[x] for x in ("1", "X", "2")) - 100) > 0.15:
            raise ValueError("Scout 1X2 probabilities do not sum to 100")
        if abs(p["GG"] + p["NG"] - 100) > 0.15:
            raise ValueError("Scout GG+NG probabilities do not sum to 100")
        top = row.get("strongest_market")
        if top not in MARKETS or p[top] < max(p.values()) - 0.05:
            raise ValueError("Scout strongest market is not actually the strongest")
        second = row.get("second_market")
        second_top = max((v for k, v in p.items() if k != top), default=-1)
        if second not in MARKETS or second == top or abs(p[second] - second_top) > 0.05:
            raise ValueError("Scout runner-up market inconsistent with six probabilities")
        ranked[fid] = row
    source_fixtures = {r["fixture_id"]: r for r in fixtures}
    used = set()
    for ticket in tickets:
        tid = ticket["id"]
        for leg in ticket.get("matches", []):
            fid = leg.get("fixture_id")
            if fid in used:
                raise ValueError("The same fixture cannot appear on A and B")
            used.add(fid)
            if fid not in ranked:
                raise ValueError("AI-approved fixture missing from all-match Scout")
            score = ranked[fid]
            pick = leg.get("pick")
            if pick != score["strongest_market"]:
                raise ValueError(
                    "AI selection uses a weaker market for " + str(fid) +
                    ": approved=" + str(pick) + " Scout top=" + score["strongest_market"]
                )
            if tid == "B" and pick != "3+":
                raise ValueError("Ticket B permits only 3+ as this match's top market")
            if not score.get("candidate_A") or (tid == "B" and not score.get("candidate_B")):
                raise ValueError("Scout says selected match is ineligible")
            item = source_fixtures[fid]
            quoted = item.get(FIELDS[pick])
            if isinstance(quoted, bool) or not isinstance(quoted, (int, float)) or not math.isfinite(quoted):
                raise ValueError("Missing source odds for Scout top market")
            try:
                approved_odd = float(leg["odd"])
            except (ValueError, TypeError, KeyError):
                raise ValueError("Selected leg missing numeric odds")
            if abs(quoted - approved_odd) > .01:
                raise ValueError("Approved quote does not equal sourced Scout top-market price")
    return {"checked": True, "matches_evaluated": len(rows),
            "market_estimates": len(rows) * len(MARKETS),
            "approved_top_market_legs": len(used),
            "report_history_sha256": scout["source_history_sha256"]}

def main():
    root = Path(".")
    approved = json.loads((root / "memarasix-1455-approved.json").read_text(encoding="utf-8"))
    if not any(x.get("id") in ("A", "B") for x in approved.get("tickets", []) if isinstance(x, dict)):
        print("SCOUT_6OF6_NBA_C_UNCHANGED")
        return 0
    try:
        data = {name: json.loads((root/"listasix-data"/(name+".json")).read_text(encoding="utf-8"))
                for name in ("active-list", "history-h2h", "sync-receipt")}
        result = validate_scout(approved, data["active-list"], data["history-h2h"],
                                data["sync-receipt"], fetch_report())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("SCOUT_6OF6_APPROVAL_BLOCKED", str(exc))
        return 1
    print("SCOUT_6OF6_ALL_ESPN_SIX_MARKETS_AND_TOP_PICKS_CONFIRMED",
          json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
