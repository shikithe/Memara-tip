#!/usr/bin/env python3
"""Offline NBA player-points research prototype. Never publishes tickets or edits bank."""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)

def evaluate(props, stats, now=None, min_games=5):
    now = now or datetime.now(timezone.utc)
    ts = utc(props["generated_at_utc"])
    if not -300 <= (now-ts).total_seconds() <= 10800:
        raise ValueError("Odds snapshot older than three hours or future-dated")
    if props.get("errors") or stats.get("errors"):
        raise ValueError("Source errors: analysis blocked")
    history = {str(p["player_id"]):p for p in stats.get("players", [])}
    results = []
    rejected = {}
    def reject(reason):
        rejected[reason] = rejected.get(reason, 0) + 1
    for offer in props.get("offers", []):
        try:
            pid = str(offer["player_id"])
            line = float(offer["points_line"])
            over, under = float(offer["over_odds"]), float(offer["under_odds"])
            if not all(math.isfinite(x) for x in (line,over,under)) or line < 0 or min(over,under) <= 1:
                reject("invalid_market"); continue
            if utc(offer["start_utc"]) <= now:
                reject("game_started"); continue
            p = history.get(pid)
            if not p:
                reject("missing_statistics"); continue
            games = sorted(p.get("recent_games", []), key=lambda g: str(g.get("game_date","")), reverse=True)
            samples = []
            for g in games:
                try:
                    pts = float(g["points"])
                    mins = float(g["minutes"])
                    if 0 <= pts <= 100 and 5 <= mins <= 60:
                        samples.append((pts,mins))
                except (TypeError, ValueError, KeyError):
                    pass
            if len(samples) < min_games:
                reject("insufficient_games"); continue
            samples = samples[:10]
            pts = [x[0] for x in samples]
            mins = [x[1] for x in samples]
            avg, sd = mean(pts), stdev(pts)
            if sd < 2:
                reject("unstable_variance"); continue
            # Exploratory normal approximation only; not validated or calibrated.
            z = (line+0.5-avg)/sd
            under_p = 0.5*(1+math.erf(z/math.sqrt(2)))
            over_p = 1-under_p
            vig = 1/over+1/under
            if vig <= 0:
                reject("invalid_market"); continue
            over_fair = (1/over)/vig
            under_fair = (1/under)/vig
            for side,prob,market_p,odds in (("OVER",over_p,over_fair,over),("UNDER",under_p,under_fair,under)):
                results.append({"player":offer["player"],"player_id":pid,"team":offer.get("team"),
                    "opponent":offer.get("opponent"),"start_utc":offer["start_utc"],
                    "side":side,"line":line,"odds":odds,"bookmaker":offer.get("bookmaker"),
                    "games_used":len(samples),"points_avg":round(avg,2),
                    "minutes_avg":round(mean(mins),2),"points_sd":round(sd,2),
                    "exploratory_probability":round(prob,4),
                    "bookmaker_no_vig_probability":round(market_p,4),
                    "exploratory_edge":round(prob-market_p,4),
                    "warning":"Uncalibrated baseline; injuries, pace and opponent defense NOT verified. Not a betting recommendation."})
        except (KeyError, ValueError, TypeError, OverflowError):
            reject("invalid_offer")
    results.sort(key=lambda x:x["exploratory_edge"],reverse=True)
    # One market per player; max twelve; never publish as validated tips.
    selected, used = [], set()
    for row in results:
        if row["player_id"] in used or row["exploratory_edge"] <= 0:
            continue
        selected.append(row); used.add(row["player_id"])
        if len(selected) == 12: break
    return {"mode":"test_only","publication_allowed":False,"analysis_status":"exploratory_uncalibrated",
        "generated_at_utc":now.isoformat(),"odds_snapshot_utc":props["generated_at_utc"],
        "statistics_snapshot_utc":stats.get("generated_at_utc"),
        "offers_examined":len(props.get("offers",[])),"eligible_sides":len(results),
        "candidates":selected,"rejections":rejected,
        "limitations":["Not calibrated against held-out NBA results","No verified injuries or lineup news",
                       "No opponent-defense or pace adjustment","Historical stats may be incomplete",
                       "No automatic publishing, bankroll changes or ticket modifications"]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--props",default="collector-output/nba-player-points.json")
    ap.add_argument("--stats",default="collector-output/nba-free-statistics.json")
    ap.add_argument("--output",default="collector-output/nba-analysis-test.json")
    args=ap.parse_args()
    props=json.loads(Path(args.props).read_text(encoding="utf-8"))
    stats=json.loads(Path(args.stats).read_text(encoding="utf-8"))
    output=evaluate(props,stats)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TEST ONLY:",len(output["candidates"]),"candidates;",output["offers_examined"],"offers checked;",output["rejections"])

if __name__=="__main__":
    main()
