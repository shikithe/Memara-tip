"""Live settlement for independent NBA SISTEM. Does not touch A/B/C.
Run repeatedly: over wins immediately above line; under loses immediately at/above line.
Over loses and under wins only at final. First irreversible missed leg loses ticket.
Only verified final DNP becomes VOID (effective odds 1.00).
"""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from nba_live_points import fetch_summary, read_state, player_points, player_did_not_play, complete_final_boxscore

PATH=Path("nba-sistem.json")
FINAL={"won","lost","void"}

def get_status(leg, doc):
    state, clock, period = read_state(doc)
    if state not in ("live","final"):
        return None
    pid=str(leg.get("player_id") or "")
    if not pid.isdigit():
        return None
    pts=player_points(doc,pid)
    if state=="final" and (player_did_not_play(doc,pid) or (pts is None and complete_final_boxscore(doc))):
        return {"status":"void","player_points":None,"effective_odd":1.0,"game_state":"final"}
    if pts is None:
        return None
    try:
        line=float(leg["points_line"])
        direction=str(leg["pick"]).lower()
        if direction not in ("over","under"):
            return None
    except (ValueError,TypeError,KeyError):
        return None
    result={"player_points":pts,"game_state":state,"game_clock":clock,"period":period}
    if direction=="over":
        if pts>line: result["status"]="won"
        elif state=="final": result["status"]="lost"
        else:result["status"]="live"
    else:
        if pts>=line:result["status"]="lost"
        elif state=="final":result["status"]="won"
        else:result["status"]="live"
    return result

def update_cycle(c, cache):
    changed=False
    for t in c.get("tickets",[]):
        if str(t.get("status","")).lower() in FINAL:
            continue
        for leg in t.get("legs",[]):
            if str(leg.get("status","")).lower() in FINAL:
                continue
            event=str(leg.get("espn_event_id") or "")
            pid=str(leg.get("player_id") or "")
            if not(event.isdigit() and pid.isdigit()):
                continue
            if event not in cache:
                try:cache[event]=fetch_summary(event)
                except (OSError,ValueError,TimeoutError,KeyError):cache[event]=None
            doc=cache[event]
            if doc is None:continue
            result=get_status(leg,doc)
            if result:
                for k,v in result.items():
                    if leg.get(k)!=v:
                        leg[k]=v
                        changed=True
        legs=t.get("legs") or []
        if len(legs)!=2:
            continue
        statuses=[str(p.get("status","pending")).lower() for p in legs]
        outcome=None
        if "lost" in statuses: outcome="lost"
        elif all(s in ("won","void") for s in statuses):
            outcome="void" if all(s=="void" for s in statuses) else "won"
        if outcome:
            t["status"]=outcome
            if outcome=="won":
                product=1.0
                for leg in legs:
                    product*=1.0 if leg.get("status")=="void" else float(leg["odd"])
                t["effective_odd"]=round(product,5)
                t["payout"]=round(float(t["stake"])*product+1e-8,2)
            elif outcome=="void":
                t["effective_odd"]=1.0
                t["payout"]=round(float(t["stake"]),2)
            else:
                t["effective_odd"]=0.0
                t["payout"]=0.0
            t["settled_at_utc"]=datetime.now(timezone.utc).isoformat()
            changed=True
    return changed

def main():
    if not PATH.exists():return
    data=json.loads(PATH.read_text(encoding="utf-8"))
    cache={}
    changed=False
    for c in data.get("cycles",[]):
        if any(str(t.get("status","pending")).lower() not in FINAL for t in c.get("tickets",[])):
            changed |= update_cycle(c,cache)
    if changed:
        PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("NBA system settlement updated.")
    else:print("NBA system no changes.")

if __name__=="__main__":
    main()
