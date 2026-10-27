"""NBA points market-line screening. Research only, no automatic bets."""
import json
from pathlib import Path

MIN_ODDS=1.75
MAX_ODDS=1.90

def analyze(offers,stats):
    by_id={str(p["player_id"]):p for p in stats["players"]}
    results=[]
    for o in offers["offers"]:
        p=by_id.get(str(o.get("player_id")))
        if not p or not p.get("complete_five"):continue
        avg=p.get("weighted_avg_points")
        minutes=p.get("avg_minutes")
        line=o.get("points_line")
        over=o.get("over_odds")
        under=o.get("under_odds")
        if any(v is None for v in (avg,minutes,line,over,under)):continue
        try:
            over,under=float(over),float(under)
        except (TypeError,ValueError):continue
        # Match BOTH sides to avoid alternative lines with artificially low odds.
        if not (MIN_ODDS<=over<=MAX_ODDS and MIN_ODDS<=under<=MAX_ODDS):continue
        delta=round(avg-float(line),2)
        if delta==0:continue
        side="OVER" if delta>0 else "UNDER"
        price=over if delta>0 else under
        risk=[]
        if p["preseason_count"]:risk.append("preseason in sample")
        if minutes<20:risk.append("low average minutes")
        if len(p["recent_games"])==5:
            pts=[g["points"] for g in p["recent_games"]]
            if max(pts)-min(pts)>=20:risk.append("volatile scoring")
        if abs(delta)<3:risk.append("small difference vs line")
        results.append({"player":o["player"],"player_id":o["player_id"],"line":line,"side":side,"odds":price,"over_odds":over,"under_odds":under,"bookmaker":o.get("bookmaker"),"weighted_avg":avg,"avg_minutes":minutes,"difference":delta,"regular_games":p["regular_count"],"preseason_games":p["preseason_count"],"risk_flags":risk,"status":"research_only","missing_checks":["injuries","confirmed lineup","opponent defense","odds movement"]})
    # Fewer flagged risks first, then closeness of the two market prices, then statistical separation.
    results.sort(key=lambda x:(len(x["risk_flags"]),abs(x["over_odds"]-x["under_odds"]),-abs(x["difference"])))
    unique={}
    for row in results:unique.setdefault(row["player_id"],row)
    selected=list(unique.values())[:12]
    return {"generated_at_utc":stats["generated_at_utc"],"source_offer_snapshot_utc":offers["generated_at_utc"],"candidate_count":len(by_id),"eligible_market_offers":len(results),"review_count":len(selected),"review_candidates":selected,"odds_range_each_side":[MIN_ODDS,MAX_ODDS],"publication_allowed":False,"method":"Both over and under odds 1.75-1.90; five-game weighted comparison; no calibrated probabilities","warning":"Research only. Missing injuries, confirmed lineups, opponent defense and odds movement. Fewer than 12 candidates are allowed."}

def main():
    offers=json.loads(Path("collector-output/nba-player-points.json").read_text())
    stats=json.loads(Path("collector-output/nba-player-stats.json").read_text())
    if stats.get("offer_snapshot_utc")!=offers.get("generated_at_utc"):raise RuntimeError("Stats and odds snapshots mismatch")
    report=analyze(offers,stats)
    target=Path("collector-output/nba-screening.json")
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"candidates":report["candidate_count"],"eligible_market_offers":report["eligible_market_offers"],"review":report["review_count"],"odds_range_each_side":report["odds_range_each_side"],"publication_allowed":False}))
if __name__=="__main__":main()
