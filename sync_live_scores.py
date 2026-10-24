#!/usr/bin/env python3
"""Read-only live results for published MemaraSix football legs.

Never edits data.json, archive.json, selections, odds, or bank. Match only
unambiguous same home/away teams and near-identical kickoff. Unmatched games
remain unverified rather than guessed. ESPN scoreboards are unofficial.
"""
import json, re, unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = "https://site.api.espn.com/apis/site/v2/sports/soccer/"
LEAGUES = ("eng.1","esp.1","ger.1","ita.1","fra.1","ned.1","por.1","sco.1","bel.1","tur.1",
           "uefa.champions","uefa.europa","uefa.europa.conf","eng.2","ger.2","ita.2")
SAR = ZoneInfo("Europe/Sarajevo")
ALIASES = {"as roma":"roma","tottenham hotspur":"tottenham","sv elversberg":"elversberg",
           "fc utrecht":"utrecht","pec zwolle":"zwolle","rb leipzig":"leipzig",
           "werder bremen":"werder bremen","st johnstone":"st johnstone"}
def norm(value):
    txt=unicodedata.normalize("NFKD",str(value)).encode("ascii","ignore").decode().lower()
    txt=re.sub(r"\b(fc|cf|sc|afc|sv|fk|ac|as|calcio|football club)\b"," ",txt)
    txt=" ".join(re.findall(r"[a-z0-9]+",txt))
    return ALIASES.get(txt,txt)

def dt(value):
    return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)

def fetch(league,day):
    qs=urlencode({"dates":day,"limit":500})
    req=Request(ROOT+league+"/scoreboard?"+qs,
                headers={"Accept":"application/json","User-Agent":"MemaraSix-Scores/1.0"})
    with urlopen(req,timeout=15) as response:return json.load(response).get("events",[])

def check_pick(pick,home,away):
    choice=str(pick).strip().upper()
    total=home+away
    if choice=="1":return home>away
    if choice=="2":return away>home
    if choice=="X":return home==away
    if choice in ("1X","X1"):return home>=away
    if choice in ("X2","2X"):return away>=home
    if choice=="12":return home!=away
    if choice in ("3+","OVER 2.5","O2.5"):return total>=3
    if choice in ("2+","OVER 1.5","O1.5"):return total>=2
    if choice=="GG":return home>0 and away>0
    if choice=="NG":return home==0 or away==0
    # Unknown markets must be judged separately; no automatic green/red.
    return None

def extract(events, league):
    parsed=[]
    for e in events:
        try:
            c=e["competitions"][0]
            competitors=c["competitors"]
            h=next(x for x in competitors if x["homeAway"]=="home")
            a=next(x for x in competitors if x["homeAway"]=="away")
            ts=dt(e.get("date") or c["date"])
            sh=int(h["score"]);sa=int(a["score"])
            state=(e.get("status") or {}).get("type") or {}
            status=state.get("state")
            finished=status=="post" and bool(state.get("completed"))
            # Only verified full-time result; penalities/extra time need review.
            detail=str(state.get("description") or "")
            display_clock=str((e.get("status") or {}).get("displayClock") or "").strip()
            short_detail=str(state.get("shortDetail") or "").strip()
            minute=None
            if status=="in":
                for candidate in (short_detail,display_clock,str(state.get("detail") or "")):
                    match=re.search(r"(?<!\d)(\d{1,3}(?:\+\d{1,2})?)\s*['′’]?(?!\d)",candidate)
                    if match and (candidate==match.group(0) or any(x in candidate.lower() for x in ("minute","min","'","′","’"))):
                        minute=match.group(1)
                        break
                if minute is None:
                    clock_match=re.fullmatch(r"(\d{1,3}):[0-5]\d",display_clock)
                    if clock_match:
                        minute=clock_match.group(1)
                if minute is None:
                    clock_value=(e.get("status") or {}).get("clock")
                    if isinstance(clock_value,(int,float)) and 0<=clock_value<=130*60:
                        minute=str(int(clock_value//60))
            if finished and re.search(r"penalt|extra time|aet",detail,re.I):
                finished=False
            parsed.append({"event_id":str(e["id"]),"league":league,"home":h["team"].get("displayName") or h["team"].get("name"),
                  "away":a["team"].get("displayName") or a["team"].get("name"),
                  "start":ts,"home_score":sh,"away_score":sa,
                  "state":"final" if finished else "live" if status=="in" else "scheduled" if status=="pre" else "unverified",
                  "detail":detail,"minute":minute if status=="in" else None})
        except (KeyError,TypeError,ValueError,IndexError,StopIteration):
            continue
    return parsed

def run(source="data.json",output="live-scores.json"):
    published=json.loads(Path(source).read_text(encoding="utf-8"))
    now=datetime.now(timezone.utc)
    matches=[(t["id"],i,m) for t in published.get("tickets",[]) for i,m in enumerate(t.get("matches",[]))]
    dates=set()
    for _,_,m in matches:
        try:
            start=dt(m.get("start_sarajevo") or m["start_utc"])
            if abs((now-start).total_seconds())<=36*3600:
                dates.add(start.astimezone(SAR).strftime("%Y%m%d"))
        except (KeyError,ValueError,TypeError):
            pass
    all_events=[];errors=[]
    for day in sorted(dates):
        for league in LEAGUES:
            try:all_events.extend(extract(fetch(league,day),league))
            except Exception:errors.append(league+":"+day)
    # Never lose a previously verified final on transient ESPN failures.
    previous = {}
    try:
        old = json.loads(Path(output).read_text(encoding="utf-8"))
        if old.get("date") == published.get("date"):
            for item in old.get("matches", []):
                if item.get("state") == "final" and item.get("source") == "espn-public-unofficial":
                    key = (item.get("ticket"),item.get("index"),item.get("home"),item.get("away"))
                    previous[key] = item
    except (OSError,ValueError,TypeError):
        pass
    results=[]
    for ticket,index,m in matches:
        record={"ticket":ticket,"index":index,"home":m.get("home"),
                "away":m.get("away"),"state":"unverified"}
        try:
            kickoff=dt(m.get("start_sarajevo") or m["start_utc"])
            candidates=[e for e in all_events
                if norm(e["home"])==norm(m.get("home")) and norm(e["away"])==norm(m.get("away"))
                and abs((e["start"]-kickoff).total_seconds())<=5400]
            unique={e["event_id"]:e for e in candidates}
            if len(unique)==1:
                e=next(iter(unique.values()))
                record.update({"state":e["state"],"score":str(e["home_score"])+":"+str(e["away_score"]),
                    "source":"espn-public-unofficial","event_id":e["event_id"],"league":e["league"],"minute":e.get("minute")})
                if e["state"]=="final":
                    outcome=check_pick(m.get("pick"),e["home_score"],e["away_score"])
                    record["result_status"]="pogođen" if outcome is True else "promašen" if outcome is False else "nepoznat"
        except (KeyError,ValueError,TypeError):
            pass
        key = (ticket,index,m.get("home"),m.get("away"))
        if key in previous and record["state"] != "final":
            record = dict(previous[key])
        results.append(record)
    payload={"date":published.get("date"),"updated_at_utc":now.isoformat(),
            "source":"espn-public-unofficial","errors_count":len(errors),
            "matches":results,"bank_unchanged":True}
    target=Path(output);target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Scores",len(results),"matched",sum(x["state"]!="unverified" for x in results),"final",sum(x["state"]=="final" for x in results),"errors",len(errors))

if __name__=="__main__":run()
