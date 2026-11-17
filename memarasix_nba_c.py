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
    """Publication-only contract: AI owns research and source confidence.

    GitHub validates structure, approval ownership, date, start times and arithmetic.
    It does not duplicate the analyst's bookmaker research or require The Odds API.
    """
    today=now.astimezone(SAR).date().isoformat()
    if approved.get("date") != today:
        raise ValueError("NBA C approval must be dated today")
    if approved.get("approval_source") != "chatgpt_ai_analyst" or approved.get("publication_allowed") is not True:
        raise ValueError("NBA C requires explicit independent AI approval")
    tickets=approved.get("tickets",[])
    if not isinstance(tickets,list) or len(tickets)!=1 or not isinstance(tickets[0],dict) or tickets[0].get("id")!="C":
        raise ValueError("NBA C must be approved independently from football A/B")
    ticket=tickets[0]
    if not isinstance(ticket.get("analysis"),str) or len(ticket["analysis"].strip())<40:
        raise ValueError("NBA C requires substantive independent AI analysis")
    if not isinstance(ticket.get("matches"),list) or len(ticket["matches"])!=2:
        raise ValueError("Ticket C must have exactly two NBA players")
    approved_at=utc(approved.get("approved_at_utc"))
    if approved_at.astimezone(SAR).date().isoformat()!=today or approved_at>now+timedelta(minutes=5):
        raise ValueError("NBA C approval timestamp invalid")
    seen=set()
    verified=[]
    total=1.0
    for leg in ticket["matches"]:
        if not isinstance(leg,dict): raise ValueError("Malformed NBA C leg")
        player=str(leg.get("player") or "").strip()
        pid=str(leg.get("player_id") or "").strip()
        event=str(leg.get("espn_event_id") or "").strip()
        if not player or not pid or not event or pid in seen:
            raise ValueError("NBA C requires exactly two distinct identified NBA players")
        seen.add(pid)
        if leg.get("market")!="player_points" or leg.get("pick") not in ("over","under"):
            raise ValueError("NBA C only supports NBA player-points over/under")
        start=utc(leg.get("start_utc"))
        if not now+timedelta(minutes=20)<start<=now+timedelta(hours=24):
            raise ValueError("NBA C game started, too close to kickoff, or outside next 24 hours")
        line=float(leg.get("points_line"))
        price=float(leg.get("odd"))
        if not 0<=line<=100 or not 1.01<price<50:
            raise ValueError("NBA C line or price invalid")
        bookmaker=str(leg.get("bookmaker") or "").strip()
        source=str(leg.get("source") or "").strip()
        if not bookmaker or not source.startswith("https://"):
            raise ValueError("AI approval must retain named bookmaker and public source URL")
        # Technical input integrity only. This is NOT an independent quote verification.
        total*=price
        team=str(leg.get("team") or "").strip()
        opponent=str(leg.get("opponent") or "").strip()
        if not team or not opponent: raise ValueError("NBA team details missing")
        verified.append({
            "fixture_id":"espn:basketball:nba:"+event+":"+pid,
            "event_id":event,"espn_event_id":event,"player_id":pid,
            "player":player,"home":team,"away":opponent,
            "team":team,"opponent":opponent,"league":"nba","sport":"basketball",
            "datetime":start.isoformat(),"start_utc":start.isoformat(),
            "market":"player_points","points_line":line,"pick":leg["pick"],
            "market_name":("Više" if leg["pick"]=="over" else "Manje")+" od "+str(line)+" poena",
            "odd":price,"bookmaker":bookmaker,"quote_source_url":source,
            "odds_status":"AI_checked_public_comparison_quote_not_live_bookmaker_confirmed",
            "quote_timestamp_verified":bool(leg.get("quote_timestamp_verified",False))
        })
    return {"date":today,"approved_at_utc":approved_at.isoformat(),
            "tickets":["C"],"nba_c":True,"verified_matches":verified,
            "combined_odds":round(total,4),"quote_verification":"ai_public_source_not_live_api"}

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
