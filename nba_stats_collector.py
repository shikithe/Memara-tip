"""MEMARA NBA last-five collector. ESPN unofficial gamelog; regular season first, then preseason."""
import argparse,datetime as dt,json,time,urllib.request
from pathlib import Path

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)

def kind(v):
    v=str(v or "").lower()
    if "pre" in v or v=="1":return "PRESEASON"
    if "regular" in v or v=="2":return "REGULAR"
    return None

def parse(payload):
    meta=payload.get("events") or {}
    if isinstance(meta,list):meta={str(x.get("id") or x.get("eventId")):x for x in meta}
    if not isinstance(meta,dict):meta={}
    rows=[]
    for season in payload.get("seasonTypes") or []:
        typ=kind(season.get("displayName") or season.get("name") or season.get("id"))
        if not typ:continue
        for cat in season.get("categories") or []:
            labels=[str(x).upper() for x in (cat.get("labels") or payload.get("labels") or payload.get("names") or [])]
            for item in cat.get("events") or []:
                eid=str(item.get("eventId") or item.get("id") or "")
                m=meta.get(eid,{})
                date=m.get("gameDate") or m.get("date") or item.get("gameDate") or item.get("date")
                stats=item.get("stats") or []
                try:
                    pi=labels.index("PTS") if "PTS" in labels else labels.index("POINTS")
                    mi=labels.index("MIN") if "MIN" in labels else labels.index("MINUTES")
                    pts=float(stats[pi]);mins=float(stats[mi])
                except (ValueError,IndexError,TypeError):continue
                if not date or not eid or mins<=0 or date[:10]>dt.datetime.now(dt.timezone.utc).date().isoformat():continue
                opp=m.get("opponent") or {}
                rows.append(dict(event_id=eid,game_date=date,season_type=typ,points=pts,minutes=mins,points_per_minute=round(pts/mins,3),opponent=opp.get("abbreviation","") if isinstance(opp,dict) else str(opp)))
    dedup={(r["event_id"],r["season_type"]):r for r in rows}
    return sorted(dedup.values(),key=lambda x:x["game_date"],reverse=True)

def select(rows):
    reg=[r for r in rows if r["season_type"]=="REGULAR"][:5]
    pre=[r for r in rows if r["season_type"]=="PRESEASON"][:5-len(reg)]
    selected=reg+pre
    def mean(k):return round(sum(r[k] for r in selected)/len(selected),2) if selected else None
    weight=len(reg)+.5*len(pre)
    return dict(recent_games=selected,regular_count=len(reg),preseason_count=len(pre),complete_five=len(selected)==5,avg_points=mean("points"),avg_minutes=mean("minutes"),weighted_avg_points=round((sum(r["points"] for r in reg)+.5*sum(r["points"] for r in pre))/weight,2) if weight else None)

def run(offers_path,output_path,season=2027,limit=0,delay=1.1,fetcher=fetch):
    offers=json.loads(Path(offers_path).read_text(encoding="utf-8"))["offers"]
    ids={}
    for o in offers:
        if o.get("player_id"):ids.setdefault(str(o["player_id"]),o.get("player") or str(o["player_id"]))
    players=[];errors=[]
    for n,(pid,name) in enumerate(list(ids.items())[:limit or None]):
        if n:time.sleep(delay)
        url=f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{pid}/gamelog?season={season}"
        try:
            record=dict(player_id=pid,player=name,source_url=url,**select(parse(fetcher(url))))
            players.append(record)
            if not record["complete_five"]:errors.append(dict(player_id=pid,reason="fewer_than_five",count=len(record["recent_games"])))
        except Exception as e:errors.append(dict(player_id=pid,reason="fetch_or_parse_failed",detail=str(e)[:180]))
    data=dict(generated_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),season=season,source="ESPN unofficial",method="regular then preseason; preseason weight 0.5",players=players,errors=errors)
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    Path(output_path).write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return data

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--offers",default="collector-output/nba-player-points.json")
    p.add_argument("--output",default="collector-output/nba-player-stats.json")
    p.add_argument("--season",type=int,default=2027)
    p.add_argument("--limit",type=int,default=0)
    a=p.parse_args();data=run(a.offers,a.output,a.season,a.limit)
    print(json.dumps(dict(players=len(data["players"]),complete=sum(x["complete_five"] for x in data["players"]),errors=data["errors"][:5])))
    if not any(x["complete_five"] for x in data["players"]):raise SystemExit(2)
