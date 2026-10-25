#!/usr/bin/env python3
"""MemaraSix point 3: conservative statistical coverage, never publish tickets."""
import argparse
import difflib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

CODES = ("PL", "ELC", "BL1", "PD", "SA", "FL1", "PPL", "DED", "BSA", "CL")
ALIASES = {"manchester united": "man united", "manchester city": "man city",
           "tottenham hotspur": "tottenham", "internazionale": "inter",
           "paris saint germain": "psg", "bayern munich": "bayern",
           "bayern munchen": "bayern"}
def norm(s):
    s = re.sub(r"[^a-z0-9 ]", " ", __import__("unicodedata").normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower())
    s = re.sub(r"\b(fc|cf|afc|sc|ac|club|football|calcio|de|the)\b", " ", s)
    s = " ".join(s.split())
    return ALIASES.get(s, s)
# Names alone are never sufficient to identify a competition across countries.
# Explicit mapping uses API-Football league IDs, not ambiguous league labels.
LEAGUE_IDS = {39:"PL",40:"ELC",78:"BL1",140:"PD",135:"SA",
              61:"FL1",94:"PPL",88:"DED",71:"BSA",2:"CL"}
def similarity(a,b):
    return difflib.SequenceMatcher(None,norm(a),norm(b)).ratio()
def resolve_pair(f, code, teams, raw_matches):
    """Require both names and a unique scheduled fixture with matching kickoff."""
    kickoff=f.get("start_utc")
    if not kickoff: return None
    try: target=datetime.fromisoformat(kickoff.replace("Z","+00:00"))
    except ValueError: return None
    options=[]
    for m in raw_matches:
        h,a=m.get("homeTeam") or {},m.get("awayTeam") or {}
        if not h.get("id") or not a.get("id") or h["id"]==a["id"]: continue
        try: when=datetime.fromisoformat(m["utcDate"].replace("Z","+00:00"))
        except (ValueError,KeyError,TypeError): continue
        if abs((when-target).total_seconds())>3*3600: continue
        hn=[h.get("name"),h.get("shortName")]
        an=[a.get("name"),a.get("shortName")]
        hs=max((similarity(f["home"],n) for n in hn if n),default=0)
        aws=max((similarity(f["away"],n) for n in an if n),default=0)
        if min(hs,aws)>=0.86 and (hs+aws)/2>=0.91:
            options.append((h["id"],a["id"],round(hs,3),round(aws,3),m.get("id")))
    return options[0] if len(options)==1 else None

def match_team(name, teams):
    key = norm(name)
    exact = [tid for tid, names in teams.items() if key in names]
    if len(exact) == 1: return exact[0], "exact"
    # Fuzzy suggestions are not trusted for automated approval.
    return None, "ambiguous" if len(exact) > 1 else "unmatched"
def get_json(code, token, season=None):
    path = f"https://api.football-data.org/v4/competitions/{code}/matches"
    if season is not None: path += f"?season={season}"
    req = urllib.request.Request(path, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.load(r)
def build_index(data, as_of):
    matches = data.get("matches", [])
    teams = {}
    for m in matches:
        for side in ("homeTeam", "awayTeam"):
            t = m.get(side) or {}
            if not t.get("id"): continue
            variants = [t.get("name"), t.get("shortName"), t.get("tla")]
            teams.setdefault(t["id"], set()).update(norm(n) for n in variants if n)
    finished = []
    for m in matches:
        if m.get("status") != "FINISHED": continue
        dt = m.get("utcDate") or ""
        try: played = datetime.fromisoformat(dt.replace("Z","+00:00"))
        except ValueError: continue
        if played >= as_of: continue
        h, a = (m.get("homeTeam") or {}).get("id"), (m.get("awayTeam") or {}).get("id")
        score = (m.get("score") or {}).get("fullTime") or {}
        if not h or not a or score.get("home") is None or score.get("away") is None: continue
        finished.append((played, h, a, score["home"], score["away"]))
    finished.sort()
    return teams, finished, matches
def stats(team, matches, side=None):
    rows = []
    for _, h, a, hg, ag in matches:
        if side == "home" and h != team: continue
        if side == "away" and a != team: continue
        if team == h: rows.append((hg, ag))
        elif team == a: rows.append((ag, hg))
    last = rows[-5:]
    return {"played":len(rows),"last5_played":len(last),
            "last5_wins":sum(g>c for g,c in last),
            "last5_draws":sum(g==c for g,c in last),
            "last5_losses":sum(g<c for g,c in last),
            "last5_goals_for":sum(g for g,c in last),
            "last5_goals_against":sum(c for g,c in last)}
def analyze(prefilter, datasets, as_of, min_total=5, min_split=2):
    result=[]
    for f in prefilter.get("fixtures",[]):
        row = {"fixture_id":f.get("fixture_id"),"league":f.get("league"),
               "home":f.get("home"),"away":f.get("away"),
               "point3":"review","reason":"competition_or_team_unmatched","coverage":None}
        if f.get("decision") == "rejected":
            row.update(point3="skipped",reason="prefilter_rejected")
        elif "women_competition_separate_track" in f.get("reasons",[]):
            row.update(reason="women_competition_separate_track")
        else:
            league_id=f.get("league_id")
            code=LEAGUE_IDS.get(league_id)
            if code is None:
                row["reason"]="competition_not_supported"
            elif code not in datasets:
                row["reason"]="competition_data_unavailable"
            else:
                teams,matches,raw_matches=datasets[code]
                home,hs=match_team(f.get("home"),teams)
                away,aw=match_team(f.get("away"),teams)
                method="exact_names"
                evidence=None
                if home is None or away is None or home==away:
                    paired=resolve_pair(f,code,teams,raw_matches)
                    if paired:
                        home,away,home_similarity,away_similarity,match_id=paired
                        method="unique_fixture_kickoff_and_names"
                        evidence={"football_data_match_id":match_id,
                                  "home_similarity":home_similarity,
                                  "away_similarity":away_similarity}
                if home is None or away is None or home==away:
                    row["reason"]="team_identity_unverified"
                else:
                    # Validate even exact names against an actual fixture whenever possible.
                    pair_confirmed=False
                    for m in raw_matches:
                        if (m.get("homeTeam") or {}).get("id")!=home or (m.get("awayTeam") or {}).get("id")!=away:
                            continue
                        try:
                            mt=datetime.fromisoformat(m["utcDate"].replace("Z","+00:00"))
                            ft=datetime.fromisoformat(f["start_utc"].replace("Z","+00:00"))
                            if abs((mt-ft).total_seconds())<=3*3600:
                                pair_confirmed=True
                                break
                        except (ValueError,KeyError,TypeError): pass
                    if not pair_confirmed:
                        row["reason"]="fixture_identity_unverified"
                    else:
                        # Cut off history at the fixture kickoff, never use post-kickoff results.
                        kickoff=datetime.fromisoformat(f["start_utc"].replace("Z","+00:00"))
                        history=[m for m in matches if m[0]<min(as_of,kickoff)]
                        h,a=stats(home,history),stats(away,history)
                        hh,aa=stats(home,history,"home"),stats(away,history,"away")
                        enough=min(h["played"],a["played"])>=min_total and hh["played"]>=min_split and aa["played"]>=min_split
                        row.update(point3="covered" if enough else "review",
                                   reason="sufficient_history" if enough else "insufficient_history",
                                   coverage={"competition":code,"match_method":method,
                                             "identity_evidence":evidence,
                                             "home_provider_id":home,"away_provider_id":away,
                                             "home_all":h,"away_all":a,
                                             "home_at_home":hh,"away_away":aa})
        result.append(row)
    counts={k:sum(r["point3"]==k for r in result) for k in ("covered","review","skipped")}
    return {"evaluated_at_utc":as_of.isoformat(),"counts":counts,"publication_allowed":False,
            "note":"Point 3 coverage only; no odds, xG, injuries or betting predictions. Exact team-name matching only. Historical results strictly before evaluation time.",
            "fixtures":result}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="collector-output/fixture-prefilter.json")
    p.add_argument("--output",default="collector-output/statistics-filter.json")
    p.add_argument("--season",type=int,default=None)
    p.add_argument("--cache-dir",default="collector-output/football-data-cache")
    p.add_argument("--offline",action="store_true")
    p.add_argument("--as-of-utc")
    a=p.parse_args()
    now=datetime.fromisoformat(a.as_of_utc.replace("Z","+00:00")) if a.as_of_utc else datetime.now(timezone.utc)
    if now.tzinfo is None: p.error("--as-of-utc must include timezone")
    now=now.astimezone(timezone.utc)
    token=os.environ.get("FOOTBALL_DATA_TOKEN","")
    if not a.offline and not token: p.error("FOOTBALL_DATA_TOKEN required unless --offline")
    pre=json.loads(Path(a.input).read_text(encoding="utf-8"))
    datasets={}
    cache=Path(a.cache_dir)
    cache.mkdir(parents=True,exist_ok=True)
    for i,code in enumerate(CODES):
        path=cache/f"{code}-{a.season or 'current'}.json"
        try:
            if a.offline: data=json.loads(path.read_text(encoding="utf-8"))
            else:
                if i: time.sleep(7)
                data=get_json(code,token,a.season)
                path.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
            datasets[code]=build_index(data,now)
            print(f"{code}: {len(datasets[code][1])} completed historical matches",flush=True)
        except (urllib.error.URLError,OSError,ValueError) as e:
            print(f"{code}: unavailable ({type(e).__name__}); coverage not assumed",flush=True)
    report=analyze(pre,datasets,now)
    report["competitions_loaded"]=list(datasets)
    dest=Path(a.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"counts":report["counts"],"competitions_loaded":list(datasets)}))
if __name__=="__main__": main()
