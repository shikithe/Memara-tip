"""Add ESPN NBA player-point states to existing football live-score snapshots.

Match strictly on ESPN event ID and athlete ID. Never infer points from team scores.
Missing or explicitly DNP boxscore entries are VOID only after a completed game and
verification of a sufficiently populated final boxscore; never invent zero points.
"""
import json
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen

API="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event="

def fetch_summary(event_id):
    req=Request(API+str(event_id),headers={"Accept":"application/json","User-Agent":"MemaraSix-NBA-Live/1.0"})
    with urlopen(req,timeout=18) as response:
        return json.load(response)

def read_state(doc):
    header=(doc.get("header") or {}).get("competitions") or []
    status=(header[0].get("status") or {}) if header else {}
    if not status: status=doc.get("status") or {}
    kind=status.get("type") or {}
    state=kind.get("state")
    completed=bool(kind.get("completed"))
    return ("final" if state=="post" and completed else "live" if state=="in" else
            "scheduled" if state=="pre" else "unverified"), str(status.get("displayClock") or ""), status.get("period")

def player_points(doc, player_id):
    found=[]
    for group in (doc.get("boxscore") or {}).get("players",[]):
        for section in group.get("statistics",[]):
            keys=[str(v).lower() for v in section.get("keys",[])]
            labels=[str(v).lower() for v in section.get("labels",[])]
            ix=next((i for i,k in enumerate(keys) if k in ("points","pts")),None)
            if ix is None: ix=next((i for i,k in enumerate(labels) if k in ("points","pts")),None)
            if ix is None: continue
            for entry in section.get("athletes",[]):
                if str((entry.get("athlete") or {}).get("id"))!=str(player_id):continue
                values=entry.get("stats") or []
                try:
                    value=int(float(values[ix]))
                    if value>=0:found.append(value)
                except (IndexError,TypeError,ValueError):pass
    return found[0] if len(found)==1 else None

def player_did_not_play(doc, player_id):
    """Use an explicit ESPN DNP/DND marker when available."""
    pid=str(player_id)
    groups=(doc.get("boxscore") or {}).get("players") or []
    for group in groups:
        sections=group.get("statistics") or []
        for section in sections:
            for entry in section.get("athletes") or []:
                if str((entry.get("athlete") or {}).get("id")) != pid:
                    continue
                reason=str(entry.get("reason") or entry.get("status") or "").upper()
                if entry.get("didNotPlay") is True or entry.get("did_not_play") is True:
                    return True
                if reason.startswith(("DNP", "DND", "DID NOT PLAY", "DID NOT DRESS")):
                    return True
    return False


def complete_final_boxscore(doc):
    """Never infer DNP from a missing/partial ESPN response."""
    teams=(doc.get("boxscore") or {}).get("players") or []
    if len(teams)!=2:
        return False
    for group in teams:
        ids={str((entry.get("athlete") or {}).get("id"))
             for section in (group.get("statistics") or [])
             for entry in (section.get("athletes") or [])
             if (entry.get("athlete") or {}).get("id") is not None}
        if len(ids)<5:
            return False
    return True


def enrich(published, records, previous, now=None, fetcher=fetch_summary):
    now=now or datetime.now(timezone.utc)
    by_event={}
    for t in published.get("tickets",[]):
        for i,m in enumerate(t.get("matches",[])):
            if m.get("sport")!="basketball" or m.get("market")!="player_points":
                continue
            key=(t.get("id"),i)
            record=next((r for r in records if (r.get("ticket"),r.get("index"))==key),None)
            if record is None:
                continue
            old=previous.get((t.get("id"),i,m.get("home"),m.get("away")))
            try:
                start=datetime.fromisoformat(str(m.get("start_utc")).replace("Z","+00:00")).astimezone(timezone.utc)
                if not -timedelta(hours=36)<=now-start<=timedelta(hours=36):
                    continue
                event_id=str(m["espn_event_id"])
                player_id=str(m["player_id"])
                if not event_id.isdigit() or not player_id.isdigit():
                    continue
                if event_id not in by_event:
                    try:
                        by_event[event_id]=fetcher(event_id)
                    except (OSError,ValueError,TimeoutError):
                        by_event[event_id]=None
                doc=by_event[event_id]
                if doc is None:
                    continue
                state,clock,period=read_state(doc)
                if state=="scheduled":
                    # A legitimate ESPN schedule is NOT a live score. Keeping
                    # this distinct from "unverified" tells the user the C
                    # event is linked and awaiting tip-off.
                    record.update({"state":"scheduled",
                                   "source":"espn-public-unofficial",
                                   "sport":"basketball",
                                   "event_id":event_id,"player_id":player_id,
                                   "points_line":float(m["points_line"]),
                                   "period":None,"game_clock":None})
                    continue
                if state not in ("live","final"):
                    continue
                pts=player_points(doc,player_id)
                dnp=state=="final" and (player_did_not_play(doc,player_id) or
                                         (pts is None and complete_final_boxscore(doc)))
                record.update({"state":state,"points_line":float(m["points_line"]),
                               "period":period,"game_clock":clock,"source":"espn-public-unofficial",
                               "event_id":event_id,"player_id":player_id,"sport":"basketball"})
                if dnp:
                    record.update({"score":"DNP","player_points":None,"void":True,
                                   "void_reason":"did_not_play","effective_odd":1.0,
                                   "result_status":"pogođen"})
                    continue
                if pts is None:
                    # Partial boxscore: no verdict, even after game end.
                    record["state"]="unverified"
                    continue
                direction=m.get("pick")
                line=float(m["points_line"])
                outcome=("pogođen" if pts>line else
                         "promašen" if state=="final" else None) if direction=="over" else (
                         "pogođen" if state=="final" and pts<line else
                         "promašen" if pts>=line else None)
                record.update({"score":str(pts),"player_points":pts})
                record.pop("void",None)
                record.pop("void_reason",None)
                record.pop("effective_odd",None)
                if outcome:
                    record["result_status"]=outcome
                else:
                    record.pop("result_status",None)
            except (KeyError,ValueError,TypeError,OverflowError):
                continue
            finally:
                # Preserve finalized results (including NBA-official verified DNP)
                # if the ESPN response is missing, incomplete or out of window.
                if old and old.get("state")=="final" and record.get("state")!="final":
                    record.clear()
                    record.update(old)
    return records
