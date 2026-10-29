#!/usr/bin/env python3
"""Conservative NBA points analyst. Research only: NEVER publishes or stakes.

Inputs: collector-output/nba-player-points.json and nba-free-statistics.json.
Optional independent, verified context JSON: player_id -> {
  expected_minutes, injury_status, opponent_defense_factor, usage_factor,
  verified_at_utc, source
}.
No context values are inferred. Probabilities are descriptive estimates, NOT
validated forecasts; unverified injuries/defense prevent a publish-ready status.
"""
import argparse
import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path("collector-output")
MIN_GAMES = 5
ODDS_MIN, ODDS_MAX = 1.75, 1.90

def timestamp(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp missing timezone")
    return dt.astimezone(timezone.utc)

def number(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None

def minutes(value):
    if isinstance(value, str) and ":" in value:
        a, b = value.split(":", 1)
        return int(a) + int(b) / 60
    return number(value)

def probability_over(line, mean, sigma):
    # Continuity-corrected normal approximation, not a calibrated NBA model.
    z = (float(line) + 0.5 - mean) / max(sigma, 4.0)
    return max(0.01, min(0.99, 0.5 * math.erfc(z / math.sqrt(2))))

def analyze(odds, stats, context=None, now=None):
    now = now or datetime.now(timezone.utc)
    context = context or {}
    players = {str(p.get("player_id")): p for p in stats.get("players", [])}
    rows, rejected = [], {}
    for offer in odds.get("offers", []):
        def reject(reason):
            rejected[reason] = rejected.get(reason, 0) + 1
        try:
            start = timestamp(offer["start_utc"])
            updated = timestamp(offer["last_update"])
        except (ValueError, KeyError, TypeError):
            reject("invalid_time")
            continue
        if not now < start <= now + timedelta(hours=24):
            reject("not_upcoming_24h")
            continue
        if updated > now + timedelta(minutes=5):
            reject("future_odds_timestamp")
            continue
        pid = str(offer.get("player_id", ""))
        p = players.get(pid)
        if not p:
            reject("no_matching_player_id")
            continue
        games = p.get("recent_games") or []
        valid = []
        for g in games[:10]:
            pts, mins = number(g.get("points")), minutes(g.get("minutes"))
            if pts is not None and mins is not None and 5 <= mins <= 60 and pts >= 0:
                valid.append((pts, mins))
        if len(valid) < MIN_GAMES:
            reject("insufficient_recent_games")
            continue
        recent = valid[:5]
        avg_points = statistics.mean(x[0] for x in valid)
        avg_minutes = statistics.mean(x[1] for x in valid)
        last5_points = statistics.mean(x[0] for x in recent)
        last5_minutes = statistics.mean(x[1] for x in recent)
        variability = statistics.stdev(x[0] for x in valid)
        ctx = context.get(pid) or {}
        verified = False
        try:
            verified = bool(ctx.get("source")) and now - timestamp(ctx["verified_at_utc"]) <= timedelta(hours=12) and timestamp(ctx["verified_at_utc"]) <= now
        except (KeyError, TypeError, ValueError):
            pass
        expected_minutes = number(ctx.get("expected_minutes")) if verified else None
        defense = number(ctx.get("opponent_defense_factor")) if verified else None
        usage = number(ctx.get("usage_factor")) if verified else None
        injury = str(ctx.get("injury_status", "")).lower() if verified else ""
        context_complete = (verified and expected_minutes is not None and
                            0.5 <= expected_minutes <= 48 and defense is not None and
                            0.75 <= defense <= 1.25 and usage is not None and
                            0.75 <= usage <= 1.25 and injury in ("available", "out", "questionable"))
        baseline = 0.65 * last5_points + 0.35 * avg_points
        if context_complete:
            projected = baseline * (expected_minutes / max(avg_minutes, 1)) * defense * usage
        else:
            projected = None
        odds_old = now - updated > timedelta(hours=3)
        for side in ("over", "under"):
            price = number(offer.get(side + "_odds"))
            line = number(offer.get("points_line"))
            if price is None or not ODDS_MIN <= price <= ODDS_MAX or line is None or line < 0:
                continue
            p_over = probability_over(line, projected, variability) if projected is not None else None
            prob = (p_over if side == "over" else 1 - p_over) if p_over is not None else None
            implied = 1 / price
            edge = prob - implied if prob is not None else None
            gaps = []
            if not context_complete:
                gaps.append("verified_minutes_injury_defense_usage_missing")
            if injury in ("out", "questionable"):
                gaps.append("player_not_confirmed_available")
            if odds_old:
                gaps.append("odds_need_revalidation")
            gaps.append("bookmaker_market_not_reverified")
            rows.append({
                "player_id": pid, "player": offer.get("player"), "team": offer.get("team"),
                "opponent": offer.get("opponent"), "espn_event_id": offer.get("espn_event_id"),
                "start_utc": start.isoformat(), "bookmaker": offer.get("bookmaker"),
                "line": line, "side": side, "odds": price,
                "sample_games": len(valid), "last5_average_points": round(last5_points, 2),
                "historical_average_points": round(avg_points, 2),
                "historical_average_minutes": round(avg_minutes, 2),
                "last5_average_minutes": round(last5_minutes, 2),
                "historical_points_stddev": round(variability, 2),
                "expected_minutes": expected_minutes if context_complete else None,
                "projected_points": round(projected, 2) if projected is not None else None,
                "estimated_probability": round(prob, 4) if prob is not None else None,
                "implied_probability": round(implied, 4),
                "estimated_edge": round(edge, 4) if edge is not None else None,
                "odds_last_update": updated.isoformat(),
                "data_gaps": gaps,
                "status": "research_only",
                "publication_allowed": False,
            })
    rows.sort(key=lambda x: (x["estimated_edge"] is None,
                              -(x["estimated_edge"] or 0), x["player"] or "", x["side"]))
    return {
        "generated_at_utc": now.isoformat(), "state": "research_only",
        "publication_allowed": False, "model": "descriptive_normal_v1_uncalibrated",
        "warning": "Not a validated probability model. Verify injuries, minutes, opponent defense and live bookmaker odds independently.",
        "input_offers": len(odds.get("offers", [])), "analyzed_markets": len(rows),
        "rejected": rejected, "candidates": rows,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--odds", default=str(ROOT / "nba-player-points.json"))
    ap.add_argument("--stats", default=str(ROOT / "nba-free-statistics.json"))
    ap.add_argument("--context", help="Optional independently verified player context JSON")
    ap.add_argument("--output", default=str(ROOT / "nba-analyst-research.json"))
    args = ap.parse_args()
    odds = json.loads(Path(args.odds).read_text(encoding="utf-8"))
    stats = json.loads(Path(args.stats).read_text(encoding="utf-8"))
    context = json.loads(Path(args.context).read_text(encoding="utf-8")) if args.context else {}
    result = analyze(odds, stats, context)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("NBA ANALYST", json.dumps({"markets": result["analyzed_markets"], "rejected": result["rejected"], "publication_allowed": False}))

if __name__ == "__main__":
    main()
