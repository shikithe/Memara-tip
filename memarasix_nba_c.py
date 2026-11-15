"""Strict independent NBA-only ticket C validation. No quote fabrication."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from memarasix_sync_listasix import canonical_hash

SAR=ZoneInfo("Europe/Sarajevo")

def utc(value):
    x=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if x.tzinfo is None: raise ValueError("Timezone required")
    return x.astimezone(timezone.utc)

def validate_nba_c(root, approved, now):
    today=now.astimezone(SAR).date().isoformat()
    if approved.get("date")!=today or approved.get("approval_source")!="chatgpt_ai_analyst" or approved.get("publication_allowed") is not True:
        raise ValueError("NBA C requires today's independent AI approval")
    tickets=approved.get("tickets")
    if not isinstance(tickets,list) or len(tickets)!=1 or tickets[0].get("id")!="C":
        raise ValueError("NBA C approval must contain exactly ticket C (publish independently)")
    ticket=tickets[0]
    if not isinstance(ticket.get("analysis"),str) or len(ticket["analysis"].strip())<40:
        raise ValueError("NBA C requires substantive analyst reasoning")
    legs=ticket.get("matches",[])
    if not isinstance(legs,list) or len(legs)!=2:
        raise ValueError("Ticket C must have exactly two NBA players")
    source=json.loads((Path(root)/"collector-output/nba-next-24h.json").read_text(encoding="utf-8"))
    props=json.loads((Path(root)/"collector-output/nba-player-points.json").read_text(encoding="utf-8"))
    if source.get("status")!="ok" or source.get("publication_allowed") is not False:
        raise ValueError("NBA player-source status invalid")
    if props.get("publication_allowed") is not False or props.get("analysis_status")!="not_run":
        raise ValueError("NBA bookmaker raw snapshot metadata invalid")
    stamp=utc(source.get("collected_at_utc"))
    generated=utc(props.get("generated_at_utc"))
    if utc(props.get("fixture_snapshot_utc"))!=stamp:
        raise ValueError("NBA odds were not generated for this ESPN fixture snapshot")
    if not (timedelta(0)<=now-generated<=timedelta(hours=3)):
        raise ValueError("NBA odds snapshot is stale")
    if not (timedelta(0)<=now-stamp<=timedelta(hours=30)):
        raise ValueError("ESPN NBA candidates stale")
    h=canonical_hash(props)
    if approved.get("source_nba_sha256")!=h:
        raise ValueError("AI approval must hash the exact verified NBA odds snapshot")
    approved_time=utc(approved.get("approved_at_utc"))
    if not generated<=approved_time<=now+timedelta(minutes=5):
        raise ValueError("NBA approval predates the bookmaker snapshot")
    if approved_time.astimezone(SAR).date().isoformat()!=today:
        raise ValueError("NBA approval is not for today")
    roster={(str(x["event_id"]),str(x["player_id"])):x for x in source.get("players",[])}
    games={str(x["event_id"]):x for x in source.get("games",[])}
    seen=set()
    validated=[]
    total=1.0
    for leg in legs:
        if not isinstance(leg,dict): raise ValueError("Malformed NBA C player")
        event=str(leg.get("espn_event_id",""))
        pid=str(leg.get("player_id",""))
        if not pid or pid in seen: raise ValueError("Ticket C must have two different NBA players")
        seen.add(pid)
        player=roster.get((event,pid))
        game=games.get(event)
        if not player or not game: raise ValueError("Player and event must match ESPN roster")
        start=utc(game["start_utc"])
        if not now+timedelta(minutes=20)<start<=now+timedelta(hours=26):
            raise ValueError("NBA game already started or is too far away")
        side=leg.get("pick")
        if side not in ("over","under") or leg.get("market")!="player_points":
            raise ValueError("NBA C supports only over/under player points")
        line=float(leg.get("points_line"))
        price=float(leg.get("odd"))
        book=str(leg.get("bookmaker_key","")).strip()
        if not 0<=line<=100 or not 1.01<price<50 or not book:
            raise ValueError("Invalid NBA line, price or bookmaker")
        candidates=[]
        for quote in props.get("offers",[]):
            if str(quote.get("player_id"))!=pid or str(quote.get("espn_event_id"))!=event:
                continue
            if str(quote.get("bookmaker_key"))!=book: continue
            if str(quote.get("player"))!=player.get("name") or str(quote.get("team"))!=player.get("team"):
                continue
            if abs(float(quote.get("points_line",-999))-line)>0.00001:continue
            if abs(float(quote.get(side+"_odds",0))-price)>0.01:continue
            try:
                updated=utc(quote.get("last_update"))
                if not now-timedelta(hours=3)<=updated<=now+timedelta(minutes=5):continue
                if abs((utc(quote.get("start_utc"))-start).total_seconds())>300:continue
            except (ValueError,TypeError): continue
            candidates.append((quote,updated))
        if len(candidates)!=1:
            raise ValueError("NBA C price must match one fresh, bookmaker-identified raw API offer")
        _,updated=candidates[0]
        total*=price
        validated.append({
            "fixture_id":"espn:basketball:nba:"+event+":"+pid,
            "event_id":event,"espn_event_id":event,"player_id":pid,
            "player":player["name"],"home":player["team"],"away":player["opponent"],
            "team":player["team"],"opponent":player["opponent"],"league":"nba",
            "sport":"basketball","datetime":start.isoformat(),"start_utc":start.isoformat(),
            "market":"player_points","points_line":line,"pick":side,
            "market_name":("Više" if side=="over" else "Manje")+" od "+str(line)+" poena",
            "odd":price,"bookmaker":book,"bookmaker_key":book,
            "odds_observed_at_utc":generated.isoformat(),
            "odds_provider_updated_at_utc":updated.isoformat()
        })
    return {"date":today,"approved_at_utc":approved_time.isoformat(),
            "tickets":["C"],"nba_c":True,"verified_matches":validated,
            "combined_odds":round(total,4)}

def nba_c_rule(ticket):
    """Lightweight policy check for unit tests; publication requires validate_nba_c."""
    if ticket.get("id")!="C" or len(ticket.get("matches",[]))!=2:
        raise ValueError("Ticket C must have exactly two NBA players")
    legs=ticket["matches"]
    if len({str(x.get("player_id","")) for x in legs})!=2 or any(
        not x.get("player_id") or x.get("market")!="player_points" or
        x.get("pick") not in ("over","under") for x in legs):
        raise ValueError("C must consist of two unique NBA player-points selections")
    return True
