#!/usr/bin/env python3
"""Independent, auditable point-3 condition matrix. Unknown != failed."""
import json
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime,timezone,timedelta
from statistics_filter import CODES,LEAGUE_IDS,build_index,get_json,match_team,resolve_pair,stats
import os,time

ROOT=Path("collector-output")
def main():
    source=json.loads((ROOT/"fixture-prefilter.json").read_text())
    rows=json.loads((ROOT/"statistics-filter.json").read_text())
    indexed={x["fixture_id"]:x for x in source["fixtures"]}
    now=datetime.fromisoformat(rows["evaluated_at_utc"])
    cache=ROOT/"football-data-cache"
    datasets={}
    for code in CODES:
        path=cache/f"{code}-current.json"
        if path.exists():
            datasets[code]=build_index(json.loads(path.read_text()),now)
    matrix=[]; totals=Counter(); patterns=Counter(); counts=Counter()
    for result in rows["fixtures"]:
        if result["point3"]!="review":continue
        f=indexed.get(result["fixture_id"],{})
        failures=[]; unknown=[]
        for reason in f.get("reasons",[]):
            if reason=="women_competition_separate_track":failures.append("women_separate_track")
        code=LEAGUE_IDS.get(f.get("league_id"))
        if code is None:
            failures.append("competition_unsupported")
            unknown.extend(["team_identity","fixture_identity","both_teams_min_5","home_min_2","away_min_2"])
        elif code not in datasets:
            unknown.extend(["competition_data","team_identity","fixture_identity","both_teams_min_5","home_min_2","away_min_2"])
        else:
            teams,history,raw=datasets[code]
            home,_=match_team(f.get("home"),teams)
            away,_=match_team(f.get("away"),teams)
            if home is None or away is None or home==away:
                paired=resolve_pair(f,code,teams,raw)
                if paired:home,away=paired[:2]
            if home is None or away is None or home==away:
                failures.append("team_identity_unverified")
                unknown.extend(["fixture_identity","both_teams_min_5","home_min_2","away_min_2"])
            else:
                pair=False
                try:
                    target=datetime.fromisoformat(f["start_utc"].replace("Z","+00:00"))
                    for m in raw:
                        if (m.get("homeTeam") or {}).get("id")!=home or (m.get("awayTeam") or {}).get("id")!=away:continue
                        dt=datetime.fromisoformat(m["utcDate"].replace("Z","+00:00"))
                        if abs((dt-target).total_seconds())<=10800:pair=True;break
                except (KeyError,TypeError,ValueError):pass
                if not pair:
                    failures.append("fixture_identity_unverified")
                    unknown.extend(["both_teams_min_5","home_min_2","away_min_2"])
                else:
                    cutoff=min(now,target)
                    played=[m for m in history if m[0]<cutoff]
                    h=stats(home,played);a=stats(away,played)
                    hh=stats(home,played,"home");aa=stats(away,played,"away")
                    if h["played"]<5:failures.append("home_team_min_5")
                    if a["played"]<5:failures.append("away_team_min_5")
                    if hh["played"]<2:failures.append("home_team_home_min_2")
                    if aa["played"]<2:failures.append("away_team_away_min_2")
        for k in failures:totals[k]+=1
        patterns[tuple(sorted(failures))]+=1
        counts[(len(failures),bool(unknown))]+=1
        matrix.append({"fixture_id":f.get("fixture_id"),"league_id":f.get("league_id"),
                       "league":f.get("league"),"home":f.get("home"),"away":f.get("away"),
                       "failed_count":len(failures),"failed_conditions":failures,
                       "not_testable_conditions":unknown})
    report={"evaluated_at_utc":now.isoformat(),"review_count":len(matrix),
            "important":"Unknown checks are NOT counted as failures. Unsupported leagues prevent independent historical checks.",
            "failed_condition_counts":dict(totals),
            "failure_combinations":[{"failed":list(k),"matches":v} for k,v in patterns.most_common()],
            "failure_count_distribution":[{"known_failures":n,"has_unknown_checks":u,"matches":v}
                                           for (n,u),v in sorted(counts.items())],
            "matches":matrix,"publication_allowed":False}
    dest=ROOT/"point3-condition-matrix.json"
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("REVIEW COUNT:",len(matrix))
    print("FAILED CONDITIONS:",json.dumps(report["failed_condition_counts"],ensure_ascii=False))
    print("COMBINATIONS:",json.dumps(report["failure_combinations"][:20],ensure_ascii=False))
    print("DISTRIBUTION:",json.dumps(report["failure_count_distribution"],ensure_ascii=False))
    print("NOTE: unknown is not a failure")
if __name__=="__main__":main()
