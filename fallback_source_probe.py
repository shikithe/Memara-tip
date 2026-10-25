#!/usr/bin/env python3
"""Read-only TheSportsDB free-tier coverage probe for unsupported competitions.
Never use partial schedules to certify point-3 history.
"""
import json, time, urllib.parse, urllib.request, urllib.error
from collections import Counter
from pathlib import Path

INPUT=Path("collector-output/statistics-filter.json")
OUTPUT=Path("collector-output/fallback-source-audit.json")
BASE="https://www.thesportsdb.com/api/v1/json/123/"
def get(endpoint, params=None):
    url=BASE+endpoint+"?"+urllib.parse.urlencode(params or {})
    request=urllib.request.Request(url,headers={"User-Agent":"MemaraSix-CoverageResearch/1.0"})
    with urllib.request.urlopen(request,timeout=30) as r:
        return json.load(r)
def main():
    rows=json.loads(INPUT.read_text(encoding="utf-8"))["fixtures"]
    unsupported=[r for r in rows if r.get("reason")=="competition_not_supported"]
    by_league=Counter(r.get("league") or "" for r in unsupported)
    # Avoid ambiguous same-name leagues. Probe a small, explicit subset only.
    selected=["Canadian Premier League","Eliteserien","CAF Champions League",
              "CAF Confederation Cup","Primera Nacional","Torneo Federal A",
              "Liga Profesional Argentina","Serie C - Girone A"]
    report={"source":"TheSportsDB v1 free","mode":"read_only_research",
            "unsupported_count":len(unsupported),"league_counts":dict(by_league),
            "probes":[],"newly_covered":0,"publication_allowed":False,
            "note":"Free tier may truncate results. No fixtures are promoted from this probe."}
    for i,name in enumerate(selected):
        if name not in by_league: continue
        if i: time.sleep(3)
        item={"league":name,"fixtures_waiting":by_league[name],"status":"not_verified"}
        try:
            response=get("search_all_leagues.php",{"c":"", "s":"Soccer"})
            # Search-all-leagues can be limited and does not prove this specific league.
            leagues=response.get("countries") or response.get("leagues") or []
            matches=[l for l in leagues if (l.get("strLeague") or "").casefold()==name.casefold()]
            item.update({"status":"listed_in_limited_directory" if len(matches)==1 else "not_confirmed_by_limited_directory",
                         "directory_matches":len(matches)})
            if len(matches)==1:
                item["provider_league_id"]=matches[0].get("idLeague")
                season=(matches[0].get("strCurrentSeason") or "")
                if season:
                    item["season"]=season
                    try:
                        events=get("eventsseason.php",{"id":item["provider_league_id"],"s":season}).get("events") or []
                        completed=[e for e in events if e.get("intHomeScore") is not None and e.get("intAwayScore") is not None]
                        item["returned_events"]=len(events)
                        item["completed_events"]=len(completed)
                        item["status"]="partial_schedule_requires_verification"
                    except (urllib.error.URLError,ValueError) as e:
                        item["schedule_error"]=type(e).__name__
        except (urllib.error.URLError,ValueError) as e:
            item["error"]=type(e).__name__
        report["probes"].append(item)
        print(json.dumps(item,ensure_ascii=False),flush=True)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FALLBACK SUMMARY:",json.dumps({"unsupported":len(unsupported),
        "probed":len(report["probes"]),"newly_covered":0}),flush=True)
if __name__=="__main__":main()
