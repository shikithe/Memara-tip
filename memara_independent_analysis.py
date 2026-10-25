#!/usr/bin/env python3
"""Independent, auditable MemaraSix candidate analysis. Never publishes bets."""
import json
import argparse
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

def parse_dt(s):
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("timezone missing")
    return d.astimezone(timezone.utc)

def goal_model(h, a):
    h, a = float(h), float(a)
    if not all(math.isfinite(x) and 0 < x <= 8 for x in (h, a)):
        raise ValueError("Invalid xG")
    total = h + a
    over = 1 - math.exp(-total) * (1 + total + total*total/2)
    return {"over_2_5": round(over, 6)}

def analyze(feed, now=None, research=None):
    now = now or datetime.now(timezone.utc)
    if feed.get("date") != now.astimezone(__import__("zoneinfo").ZoneInfo("Europe/Sarajevo")).date().isoformat():
        raise ValueError("Collector feed is not for today's Sarajevo date")
    generated = parse_dt(feed["generated_at_utc"])
    if generated > now + timedelta(minutes=5) or now - generated > timedelta(hours=6):
        raise ValueError("Collector feed is stale or timestamp invalid")
    research = research or {}
    matched = {}
    if research.get("date") == feed["date"]:
        for item in research.get("football", {}).get("fixtures", []):
            key = (str(item.get("home","")).casefold(),str(item.get("away","")).casefold())
            matched[key] = item
    report = {"date":feed["date"], "generated_at_utc":now.isoformat(),
              "source_generated_at_utc":feed["generated_at_utc"],
              "state":"analysis_completed_data_gaps_remain",
              "publication_allowed":False, "odds_verified":False,
              "football":[], "nba":[], "summary":{}}
    for sport, key, out in (("football","football_candidates","football"),("nba","nba_games","nba")):
        seen = set()
        for f in feed.get(key, []):
            ident = str(f.get("id",""))
            if not ident or ident in seen:
                continue
            seen.add(ident)
            issues = []
            try:
                start = parse_dt(f["start_utc"])
                if start <= now + timedelta(minutes=10):
                    issues.append("started_or_too_close_to_kickoff")
            except (ValueError,KeyError,TypeError):
                issues.append("invalid_start_time")
            if f.get("status") != "pre":
                issues.append("not_pre_match")
            if not f.get("home") or not f.get("away") or f.get("home") == f.get("away"):
                issues.append("invalid_teams")
            if f.get("coverage","").startswith("incomplete"):
                issues.append("incomplete_provider_coverage")
            issues.extend(["missing_verified_recent_form","missing_verified_lineups_or_absences",
                           "missing_verified_market_odds"])
            item = matched.get((str(f.get("home","")).casefold(),str(f.get("away","")).casefold())) if sport == "football" else None
            model = None
            if item:
                hs, aw = item.get("home_stats") or {}, item.get("away_stats") or {}
                try:
                    if hs.get("xg_for_avg") is not None and aw.get("xg_for_avg") is not None:
                        model = goal_model(hs["xg_for_avg"], aw["xg_for_avg"])
                except (TypeError, ValueError, OverflowError):
                    pass
            report[out].append({"id":ident,"home":f.get("home"),"away":f.get("away"),
                "start_utc":f.get("start_utc"),"league":f.get("league"),
                "eligible_for_further_research":"started_or_too_close_to_kickoff" not in issues and
                    "invalid_start_time" not in issues and "not_pre_match" not in issues and
                    "invalid_teams" not in issues,
                "data_gaps":issues,"model_probability":model,
                "recommended_market":None,"analysis_status":"needs_independent_evidence"})
    report["football"].sort(key=lambda x:(x["model_probability"] is None, not x["eligible_for_further_research"],len(x["data_gaps"])))
    report["summary"] = {k:{"total":len(report[k]),"researchable":sum(x["eligible_for_further_research"] for x in report[k])} for k in ("football","nba")}
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--feed",default="collector-feed.json")
    p.add_argument("--output",default="collector-output/independent-analysis.json")
    p.add_argument("--research",default="collector-output/statistics-research.json")
    args=p.parse_args()
    research_path=Path(args.research)
    research=json.loads(research_path.read_text(encoding="utf-8")) if research_path.exists() else {}
    report=analyze(json.loads(Path(args.feed).read_text(encoding="utf-8")),research=research)
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["summary"]))

if __name__=="__main__":
    main()
