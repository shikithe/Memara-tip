#!/usr/bin/env python3
"""MemaraSix PreScout -> Advanced Scout, read-only with respect to tickets/bank.

Requires today's ListaSix active offer and a compact ESPN evidence brief.
No probabilities are inferred from bookmaker odds. Missing verified scores means
NO model percentage, not a guess. Output is research-only, never publication.
"""
import argparse
import json
import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SAR = ZoneInfo("Europe/Sarajevo")
MARKETS = {
    "1": "home_odds", "X": "draw_odds", "2": "away_odds",
    "2+": "over15_odds", "3+": "over25_odds", "BTTS": "btts_yes_odds"
}
MAX_SHORTLIST = 10


def timestamp(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp lacks timezone")
    return dt.astimezone(timezone.utc)


def norm(value):
    s = unicodedata.normalize("NFKD", str(value or "").casefold())
    return re.sub(r"[^a-z0-9]", "", s.encode("ascii", "ignore").decode())


def form_rows(side):
    """Return only provable final-score records, never infer from a fixture name."""
    name = norm(side.get("name"))
    result = []
    seen = set()
    for m in (side.get("last_five_matches") or [])[:5]:
        if not isinstance(m, dict) or not isinstance(m.get("scores"), dict):
            continue
        eid = str(m.get("event_id") or "")
        if not eid or eid in seen:
            continue
        score = m["scores"]
        h, a = score.get("home"), score.get("away")
        if any(isinstance(v, bool) or not isinstance(v, (int, float, str)) for v in (h, a)):
            continue
        if not re.fullmatch(r"\d{1,2}", str(h)) or not re.fullmatch(r"\d{1,2}", str(a)):
            continue
        if int(h) > 12 or int(a) > 12:
            continue
        match = m.get("match") or ""
        # ESPN uses "Away Team at Home Team". Refuse ambiguous team names.
        sides = re.split(r"\s+at\s+", match, maxsplit=1, flags=re.IGNORECASE)
        if len(sides) != 2:
            continue
        is_home = norm(sides[1]) == name
        is_away = norm(sides[0]) == name
        if is_home == is_away:
            continue
        own, conceded = ((int(h), int(a)) if is_home else (int(a), int(h)))
        seen.add(eid)
        result.append({"scored": own, "conceded": conceded,
                       "home": is_home, "event_id": eid,
                       "date": m.get("date"), "competition": m.get("competition")})
    return result


def profile(rows, venue):
    if len(rows) < 4:
        return None
    by_venue = [r for r in rows if r["home"] == venue]
    if len(by_venue) < 2:
        return None
    def rate(group, field):
        return sum(r[field] for r in group) / len(group)
    # Venue weighted form with modest shrinkage; heuristic, NOT trained/calibrated.
    return {
        "scored": .65 * rate(by_venue, "scored") + .35 * rate(rows, "scored"),
        "conceded": .65 * rate(by_venue, "conceded") + .35 * rate(rows, "conceded"),
        "venue_count": len(by_venue), "verified_count": len(rows)
    }


def probabilities(home_x, away_x):
    if not all(math.isfinite(v) and 0.1 <= v <= 5 for v in (home_x, away_x)):
        raise ValueError("Unsafe goal expectations")
    h = [math.exp(-home_x) * home_x**i / math.factorial(i) for i in range(16)]
    a = [math.exp(-away_x) * away_x**i / math.factorial(i) for i in range(16)]
    p1 = sum(h[i] * a[j] for i in range(16) for j in range(i))
    px = sum(h[i] * a[i] for i in range(16))
    p2 = max(0., 1. - p1 - px)
    t = home_x + away_x
    return {
        "1": p1, "X": px, "2": p2,
        "2+": 1 - math.exp(-t) * (1 + t),
        "3+": 1 - math.exp(-t) * (1 + t + t*t/2),
        "BTTS": (1 - math.exp(-home_x)) * (1 - math.exp(-away_x))
    }


def positive_number(value):
    try:
        if isinstance(value, bool) or value is None:
            return None
        v = float(value)
        return v if math.isfinite(v) and 0 < v <= 8 else None
    except (TypeError, ValueError):
        return None


def verified_extra(entry, now):
    """Independent research must document dated sources; flags alone are insufficient."""
    if not isinstance(entry, dict):
        return {}
    try:
        if timestamp(entry["verified_at_utc"]).date() != now.date():
            return {}
    except (ValueError, KeyError, TypeError):
        return {}
    def sourced(section):
        block = entry.get(section)
        if not isinstance(block, dict):
            return None
        urls = block.get("sources")
        if not isinstance(urls, list) or not urls or not all(
            isinstance(u, str) and u.startswith("https://") and len(u) > 10 for u in urls
        ):
            return None
        return block
    xg = sourced("xg")
    if xg and all(positive_number(xg.get(key)) is not None for key in (
        "home_xg_for", "home_xg_against", "away_xg_for", "away_xg_against"
    )):
        pass
    else:
        xg = None
    team_news = sourced("team_news")
    if team_news and team_news.get("lineups_checked") is True and team_news.get("absences_checked") is True:
        pass
    else:
        team_news = None
    return {"xg": xg, "team_news": team_news}


def analyze(offer, brief, research=None, now=None, limit=MAX_SHORTLIST):
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    today = now.astimezone(SAR).date().isoformat()
    if offer.get("date") != today or offer.get("publication_allowed") is not True:
        raise ValueError("Today's approved ListaSix offer is missing")
    if timestamp(offer["expires_at"]) <= now:
        raise ValueError("ListaSix offer expired")
    if not isinstance(offer.get("fixtures"), list) or not offer["fixtures"]:
        raise ValueError("No ListaSix fixtures")
    # An absent brief is NOT a green light to use implied market probabilities.
    valid_brief = isinstance(brief, dict) and brief.get("date") == today and isinstance(brief.get("fixtures"), list)
    by_id = {str(x.get("fixture_id")): x for x in brief["fixtures"] if isinstance(x, dict)} if valid_brief else {}
    independent = (research or {}).get("fixtures") or {}
    if (research or {}).get("date") != today or not isinstance(independent, dict):
        independent = {}
    prescout = []
    seen = set()
    for fixture in offer["fixtures"]:
        fid = str(fixture.get("fixture_id") or "")
        if not fid or fid in seen:
            continue
        seen.add(fid)
        row = {"fixture_id": fid, "match": fixture.get("match"), "start_utc": fixture.get("datetime"),
               "prescout_status": "not_evaluated", "data_gaps": [],
               "markets": [], "recommended_market": None, "model_source": None}
        try:
            kickoff = timestamp(fixture["datetime"])
            if kickoff <= now + timedelta(minutes=10):
                row["prescout_status"] = "started_or_less_than_10min"
                prescout.append(row)
                continue
        except (KeyError, ValueError, TypeError):
            row["prescout_status"] = "invalid_kickoff"
            prescout.append(row)
            continue
        entry = by_id.get(fid)
        if entry is None:
            row["data_gaps"].append("missing_matching_daily_espn_brief")
            row["prescout_status"] = "insufficient_evidence"
            prescout.append(row)
            continue
        home_rows = form_rows(entry.get("home_form") or {})
        away_rows = form_rows(entry.get("away_form") or {})
        hp = profile(home_rows, True)
        ap = profile(away_rows, False)
        row["form_verified"] = {"home": len(home_rows), "away": len(away_rows),
                                "home_home_games": sum(r["home"] for r in home_rows),
                                "away_away_games": sum(not r["home"] for r in away_rows)}
        if hp is None or ap is None:
            row["data_gaps"].append("need_four_real_scores_and_two_venue_matches_per_team")
            row["prescout_status"] = "insufficient_evidence"
            prescout.append(row)
            continue
        extra = verified_extra(independent.get(fid), now)
        if extra.get("xg"):
            xg = extra["xg"]
            lh = .5 * (float(xg["home_xg_for"]) + float(xg["away_xg_against"]))
            la = .5 * (float(xg["away_xg_for"]) + float(xg["home_xg_against"]))
            model_name = "sourced_xg_independent_poisson_uncalibrated"
        else:
            # Empirical recent-score rates, no bookmaker numbers in estimation.
            lh = .5 * (hp["scored"] + ap["conceded"])
            la = .5 * (ap["scored"] + hp["conceded"])
            model_name = "observed_goals_independent_poisson_uncalibrated"
        lh, la = max(.2, min(4.8, lh)), max(.2, min(4.8, la))
        model = probabilities(lh, la)
        row["expected_goals"] = {"home": round(lh, 3), "away": round(la, 3)}
        row["model_source"] = model_name
        row["data_confidence_score"] = min(55, 5.5 * (len(home_rows) + len(away_rows)))
        row["data_confidence_score"] += 10 if hp["venue_count"] >= 2 and ap["venue_count"] >= 2 else 0
        row["data_confidence_score"] += 5 if entry.get("head_to_head", {}).get("found", 0) > 0 else 0
        row["data_confidence_score"] += 15 if extra.get("xg") else 0
        row["data_confidence_score"] += 15 if extra.get("team_news") else 0
        row["data_confidence_score"] = round(row["data_confidence_score"])
        if not extra.get("xg"):
            row["data_gaps"].append("verified_xg_xga_missing")
        if not extra.get("team_news"):
            row["data_gaps"].append("verified_lineups_and_absences_missing")
        if not entry.get("head_to_head", {}).get("found"):
            row["data_gaps"].append("h2h_unavailable_low_weight")
        for market, price_field in MARKETS.items():
            odds = positive_number(fixture.get(price_field))
            if odds is None or odds <= 1:
                continue
            p = model[market]
            row["markets"].append({"type": market, "probability": round(p, 4),
                                   "odds_snapshot": odds,
                                   "estimated_ev": round(p*odds-1, 4)})
        row["markets"].sort(key=lambda v: (-v["probability"], v["type"]))
        if row["markets"]:
            row["recommended_market"] = row["markets"][0]["type"]
            row["prescout_status"] = "shortlist_candidate"
        else:
            row["data_gaps"].append("no_valid_offered_markets")
            row["prescout_status"] = "insufficient_evidence"
        prescout.append(row)
    candidates = sorted((x for x in prescout if x["prescout_status"] == "shortlist_candidate"),
                        key=lambda r: (-r["markets"][0]["probability"], -r["data_confidence_score"], r["fixture_id"]))[:limit]
    scout = []
    for r in candidates:
        confidence = r["data_confidence_score"]
        ready = confidence >= 80 and not any(s in r["data_gaps"] for s in (
            "verified_xg_xga_missing", "verified_lineups_and_absences_missing"))
        scout.append({"fixture_id": r["fixture_id"], "match": r["match"],
                      "start_utc": r["start_utc"], "best_market": r["recommended_market"],
                      "markets": r["markets"], "model_source": r["model_source"],
                      "expected_goals": r["expected_goals"],
                      "data_confidence_score": confidence, "data_gaps": r["data_gaps"],
                      "scout_status": "ready_for_human_verification" if ready else "needs_advanced_scout_evidence",
                      "approved_for_ticket": False})
    return {
        "schema_version": "memarasix-pre-scout-advanced-scout-v1",
        "date": today, "generated_at_utc": now.isoformat(),
        "offer_fixture_count": len(offer["fixtures"]),
        "brief_available": valid_brief,
        "pre_scout": prescout, "scout_candidates": scout,
        "summary": {"future": sum(x["prescout_status"] not in ("started_or_less_than_10min","invalid_kickoff") for x in prescout),
                    "modelled": sum(x["prescout_status"]=="shortlist_candidate" for x in prescout),
                    "shortlisted": len(scout),
                    "awaiting_data": sum(x["prescout_status"]=="insufficient_evidence" for x in prescout),
                    "ready_for_human_verification": sum(x["scout_status"]=="ready_for_human_verification" for x in scout)},
        "selection_basis": "Independently modelled probability, never low bookmaker odds",
        "model_limitation": "Heuristic independent Poisson; not backtested or calibrated. Percentages are provisional.",
        "publication_allowed": False, "tickets_modified": False,
        "bank_modified": False, "archive_modified": False
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--offer", default="listasix-data/active-list.json")
    p.add_argument("--brief", default="listasix-data/analysis-brief.json")
    p.add_argument("--research", default="collector-output/scout-independent-evidence.json")
    p.add_argument("--output", default="collector-output/scout-report.json")
    args = p.parse_args()
    offer = json.loads(Path(args.offer).read_text(encoding="utf-8"))
    brief_path = Path(args.brief)
    brief = json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else None
    research_path = Path(args.research)
    research = json.loads(research_path.read_text(encoding="utf-8")) if research_path.exists() else None
    report = analyze(offer, brief, research=research)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("SCOUT_RESEARCH_ONLY", json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
