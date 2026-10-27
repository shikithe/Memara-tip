"""Conservative NBA points screening, not an automatic betting recommendation."""
import json,math
from pathlib import Path
def analyze(offers,stats):
    by_id={str(p["player_id"]):p for p in stats["players"]}
    results=[]
    for o in offers["offers"]:
        p=by_id.get(str(o.get("player_id")))
        if not p or not p.get("complete_five"):continue
        avg=p.get("weighted_avg_points")
        minutes=p.get("avg_minutes")
        line=o.get("points_line")
        if avg is None or line is None or minutes is None:continue
        # Require meaningful separation and sufficient minutes; no invented win probability.
        delta=round(avg-float(line),2)
        side="OVER" if delta>0 else "UNDER"
        price=o.get("over_odds" if delta>0 else "under_odds")
        if price is None or not (1.3<=float(price)<=5.0):continue
        risk=[]
        if p["preseason_count"]:risk.append("preseason in sample")
        if minutes<20:risk.append("low average minutes")
        if len(p["recent_games"])==5:
            pts=[g["points"] for g in p["recent_games"]]
            if max(pts)-min(pts)>=20:risk.append("volatile scoring")
        if abs(delta)<3:risk.append("small edge vs line")
        results.append({"player":o["player"],"player_id":o["player_id"],"line":line,"side":side,"odds":price,"bookmaker":o.get("bookmaker"),"weighted_avg":avg,"avg_minutes":minutes,"difference":delta,"regular_games":p["regular_count"],"preseason_games":p["preseason_count"],"risk_flags":risk,"status":"research_only","missing_checks":["injuries","confirmed lineup","opponent defense","odds movement"]})
    results.sort(key=lambda x:(len(x["risk_flags"]),-abs(x["difference"])))
    # Deduplicate across bookmakers; max 12 distinct players for review.
    unique={}
    for row in results:unique.setdefault(row["player_id"],row)
    return {"generated_at_utc":stats["generated_at_utc"],"source_offer_snapshot_utc":offers["generated_at_utc"],"candidate_count":len(by_id),"review_candidates":list(unique.values())[:12],"publication_allowed":False,"method":"five-game weighted comparison; no calibrated probabilities","warning":"Screening only. Missing injuries, confirmed lineups, opponent defense and odds movement."}
def main():
    offers=json.loads(Path("collector-output/nba-player-points.json").read_text())
    stats=json.loads(Path("collector-output/nba-player-stats.json").read_text())
    if stats.get("offer_snapshot_utc")!=offers.get("generated_at_utc"):raise RuntimeError("Stats and odds snapshots mismatch")
    report=analyze(offers,stats)
    target=Path("collector-output/nba-screening.json")
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"candidates":report["candidate_count"],"review":len(report["review_candidates"]),"publication_allowed":False}))
if __name__=="__main__":main()
