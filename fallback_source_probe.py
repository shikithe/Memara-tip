#!/usr/bin/env python3
"""MemaraSix fallback league discovery v2: country, tier, stage and names.
Research only: never certify coverage from a league-name match.
"""
import json,re,time,unicodedata,urllib.parse,urllib.request,urllib.error
from collections import Counter,defaultdict
from pathlib import Path
from difflib import SequenceMatcher

ROOT=Path("collector-output")
BASE="https://www.thesportsdb.com/api/v1/json/123/"
def get(endpoint,params=None):
    url=BASE+endpoint+"?"+urllib.parse.urlencode(params or {})
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"MemaraSix-LeagueAudit/2.0"}),timeout=35) as r:return json.load(r)
def norm(s):
    s=unicodedata.normalize("NFKD",str(s or "")).encode("ascii","ignore").decode().casefold()
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return " ".join(s.split())
def stage(s):
    n=norm(s)
    if re.search(r"\bclausura\b",n):return "clausura"
    if re.search(r"\bapertura\b",n):return "apertura"
    return None
def tier(s):
    n=norm(s)
    if re.search(r"\b(segunda|second|serie b|primera nacional|championship)\b",n):return 2
    if re.search(r"\b(tercera|third|serie c|torneo federal a)\b",n):return 3
    if re.search(r"\b(primera|first|premier|serie a|liga profesional|eliteserien)\b",n):return 1
    return None
def family(s):
    n=norm(s)
    for x in ("apertura","clausura","torneo","campeonato","league","liga","division","de","del","the"):
        n=re.sub(r"\b"+x+r"\b"," ",n)
    return " ".join(n.split())
def rank(source,candidate,country):
    name=candidate.get("strLeague") or ""
    a,b=norm(source),norm(name)
    score=max(SequenceMatcher(None,a,b).ratio(),SequenceMatcher(None,family(source),family(name)).ratio()*0.92)
    source_stage,candidate_stage=stage(source),stage(name)
    if source_stage and candidate_stage and source_stage!=candidate_stage:return None
    if source_stage and not candidate_stage:score-=0.18
    if not source_stage and candidate_stage:score-=0.10
    st,ct=tier(source),tier(name)
    if st and ct and st!=ct:return None
    provider_country=norm(candidate.get("strCountry"))
    if country and provider_country and norm(country)!=provider_country:return None
    if country and not provider_country:score-=0.12
    return round(score,3)
def main():
    results=json.loads((ROOT/"statistics-filter.json").read_text())["fixtures"]
    original=json.loads((ROOT/"statistics-research.json").read_text())["football"]["fixtures"]
    lookup={x.get("fixture_id"):x for x in original}
    pending=[r for r in results if r.get("reason")=="competition_not_supported"]
    groups=defaultdict(list)
    for r in pending:
        f=lookup.get(r["fixture_id"],{})
        groups[(f.get("league_id"),f.get("league_name") or r.get("league"))].append(r)
    report={"mode":"read_only_league_discovery_v2","pending":len(pending),
            "league_groups":len(groups),"newly_covered":0,"publication_allowed":False,
            "note":"Candidate names are not verified league identities. Country unavailable in source is explicitly unknown.",
            "leagues":[]}
    try:
        catalog=get("all_leagues.php").get("leagues") or []
        catalog=[x for x in catalog if norm(x.get("strSport")) in ("soccer","football")]
        print("THE SPORTS DB CATALOG:",len(catalog),flush=True)
    except (urllib.error.URLError,ValueError,KeyError) as e:
        print("CATALOG ERROR:",type(e).__name__,flush=True)
        catalog=[]
    for (league_id,name),fixtures in sorted(groups.items(),key=lambda x:-len(x[1])):
        # Do not infer country from ambiguous league names.
        # Some API-Football league IDs have independently established countries.
        known_countries={129:"Argentina",134:"Argentina",103:"Norway",12:None,20:None,
                         570:None,39:"England",61:"France",71:"Brazil",140:"Spain"}
        country=known_countries.get(league_id)
        options=[]
        for entry in catalog:
            score=rank(name,entry,country)
            if score is not None and score>=0.58:
                options.append({"id":entry.get("idLeague"),"name":entry.get("strLeague"),
                                "country":entry.get("strCountry"),"score":score})
        options.sort(key=lambda x:-x["score"])
        top=options[:3]
        item={"api_football_league_id":league_id,"league":name,"fixtures":len(fixtures),
              "country":country,"stage":stage(name),"tier":tier(name),
              "status":"candidate_only" if top else "not_found_in_catalog",
              "candidates":top}
        report["leagues"].append(item)
        print("LEAGUE:",json.dumps(item,ensure_ascii=False),flush=True)
    (ROOT/"fallback-source-audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FALLBACK SUMMARY:",json.dumps({"unsupported":len(pending),"league_groups":len(groups),
          "catalog_entries":len(catalog),"candidate_groups":sum(bool(x["candidates"]) for x in report["leagues"]),
          "newly_covered":0}),flush=True)
if __name__=="__main__":main()
