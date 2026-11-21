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
    # Cross-check the exact handoff list: 10 strongest eligible matches only.
    # The ranked matrix still contains all matches, but detailed research does not
    # repeat the earlier Poisson, five-game and home/away calculations.
    expected_top_ten = [
        row["fixture_id"]
        for row in sorted(
            (row for row in rows if row.get("candidate_A")),
            key=lambda r: (-r["strongest_pct"], -r["second_pct"],
                           -r.get("third_pct", 0), r["fixture_id"])
        )[:10]
    ]
    handoff = scout.get("detailed_ai_handoff", {})
    received = handoff.get("candidates", []) if isinstance(handoff, dict) else []
    forwarded = [r.get("fixture_id") for r in received if isinstance(r, dict)]
    if not expected_top_ten or forwarded != expected_top_ten:
        raise ValueError("Detailed AI handoff must contain exactly the TOP 10 eligible fixtures in order")
    if scout.get("detailed_ai_top_ten_fixture_ids") != expected_top_ten:
        raise ValueError("Detailed AI top ten ID list mismatch")
    if handoff.get("math_recalculation_prohibited") is not True:
        raise ValueError("Do not repeat previous mathematical Scout analysis")

    # The AI must document research on all ten candidates, including rejected
    # ones. These fields deliberately exclude prior five-match/goals/form math.
    review = approval.get("detailed_ai_review", {})
    reviewed = review.get("candidates", []) if isinstance(review, dict) else []
    if not isinstance(reviewed, list) or len(reviewed) != len(expected_top_ten):
        raise ValueError("AI must review all ten handed-off candidates before A/B approval")
    if review.get("source_active_sha256") != scout.get("source_active_sha256") or \
       review.get("source_history_sha256") != scout.get("source_history_sha256"):
        raise ValueError("Detailed AI review must use exactly the same Scout source snapshots")
    mandatory = {
        "xg_xga", "injuries_suspensions", "expected_lineups", "h2h",
        "motivation_table", "rest_schedule", "quote_source"
    }
    review_by_id = {}
    for item in reviewed:
        if not isinstance(item, dict):
            raise ValueError("Malformed detailed AI review candidate")
        fid = item.get("fixture_id")
        if fid in review_by_id:
            raise ValueError("Duplicate candidate in detailed AI review")
        if fid not in expected_top_ten:
            raise ValueError("Detailed AI reviewed a fixture outside top ten")
        if item.get("decision") not in ("approved", "rejected", "uncertain"):
            raise ValueError("Detailed AI decision missing")
        if len(str(item.get("review_summary", "")).strip()) < 40:
            raise ValueError("Substantive independent AI review summary missing")
        factors = item.get("new_factors")
        if not isinstance(factors, dict) or set(factors) != mandatory:
            raise ValueError("Detailed AI review must cover seven NEW factors, not repeat mathematical Scout work")
        for name, value in factors.items():
            if not isinstance(value, dict) or value.get("status") not in ("verified", "unavailable"):
                raise ValueError("Missing verified/unavailable evidence status for " + name)
            if not str(value.get("notes", "")).strip():
                raise ValueError("Each new-factors check must give real evidence or explicitly note unavailable")
            if value["status"] == "verified" and not isinstance(value.get("source_url"), str):
                raise ValueError("Verified new factor must name a public source URL")
        review_by_id[fid] = item
    if set(review_by_id) != set(expected_top_ten):
        raise ValueError("Every top-ten handoff fixture must receive an AI review")

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
            if fid not in expected_top_ten:
                raise ValueError("AI-approved fixture is OUTSIDE the ten strongest eligible candidates")
            if review_by_id[fid].get("decision") != "approved":
                raise ValueError("AI selected a top-ten fixture without detailed review approval")
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
