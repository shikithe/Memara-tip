#!/usr/bin/env python3
"""Settle published *virtual* tickets from unambiguous verified final score data.

Idempotent: derives the balance from original after-stakes balance plus the
payouts of settled tickets. No event is paid twice on repeated execution.
Preserves selections and stakes; a verified DNP changes only its effective leg
odds to 1.00 and recalculates ticket odds. Does not edit archive.
"""
import argparse
import copy
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

CENT = Decimal("0.01")

def amount(value):
    if isinstance(value, bool):
        raise ValueError("Boolean cannot be monetary value")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid money or odds")
    if not number.is_finite() or number < 0:
        raise ValueError("Invalid money or odds")
    return number

def cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)

def settle(published, snapshot):
    if published.get("date") != snapshot.get("date"):
        raise ValueError("Live results belong to another publication date")
    if snapshot.get("source") != "espn-public-unofficial":
        raise ValueError("Score provenance invalid")
    updated = datetime.fromisoformat(snapshot["updated_at_utc"].replace("Z","+00:00"))
    if updated.tzinfo is None:
        raise ValueError("Score timestamp missing timezone")
    original = copy.deepcopy(published)
    outcomes = {}
    for record in snapshot.get("matches",[]):
        key = (str(record.get("ticket")),record.get("index"))
        if key in outcomes:
            raise ValueError("Ambiguous duplicate score record")
        outcomes[key] = record
    base = amount(original.get("bank_after_stakes", original["bank_after"]))
    before = amount(original["bank_before"])
    total_stakes = sum((amount(t.get("stake",0)) for t in original.get("tickets", [])),Decimal(0))
    if abs(cents(before - total_stakes)-cents(base)) > CENT:
        raise ValueError("Bank-after-stakes does not reconcile")
    newly_settled = []
    # Provisional credit only for verified live goal thresholds; recalculated on every run.
    def early_goals_hit(match, rec):
        if not rec or rec.get("state") not in ("live", "final"):
            return False
        if rec.get("source") != "espn-public-unofficial" or not str(rec.get("event_id", "")).isdigit():
            return False
        if rec.get("home") != match.get("home") or rec.get("away") != match.get("away"):
            return False
        threshold = {"3+":3, "OVER 2.5":3, "O2.5":3,
                     "2+":2, "OVER 1.5":2, "O1.5":2}.get(str(match.get("pick","")).strip().upper())
        if threshold is None:
            return False
        parts = str(rec.get("score","")).split(":")
        return len(parts)==2 and all(x.isdigit() for x in parts) and sum(map(int,parts))>=threshold

    for ticket in original.get("tickets",[]):
        if ticket.get("status") not in ("objavljen","aktivan","dobitan","izgubljen"):
            continue
        legs=[]
        for index,match in enumerate(ticket.get("matches",[])):
            rec=outcomes.get((str(ticket["id"]),index))
            if not rec or rec.get("home")!=match.get("home") or rec.get("away")!=match.get("away"):
                legs.append(None)
                continue
            if rec.get("source") not in ("espn-public-unofficial","nba-official-scorers-report"):
                legs.append(None)
                continue
            if rec.get("source")=="nba-official-scorers-report" and not (match.get("sport")=="basketball" and rec.get("void") is True and rec.get("verification_source_url")):
                legs.append(None)
                continue
            if match.get("sport")=="basketball" and match.get("market")=="player_points":
                if rec.get("sport")!="basketball" or str(rec.get("event_id"))!=str(match.get("espn_event_id")) or str(rec.get("player_id"))!=str(match.get("player_id")):
                    legs.append(None)
                    continue
                if rec.get("state") not in ("live","final"):
                    legs.append(None)
                    continue
                if rec.get("void") is True:
                    # VOID is a winning/neutral leg, not a zero-point UNDER hit.
                    # It can only settle when the whole game is FINAL.
                    if rec["state"]!="final" or rec.get("void_reason")!="did_not_play" or rec.get("player_points") is not None:
                        legs.append(None)
                        continue
                    if match.get("result_status")=="promašen" or (match.get("final_points") is not None and "final_points" in match):
                        raise ValueError("DNP conflicts with previously locked player result")
                    if match.get("original_odd") is None:
                        match["original_odd"]=match.get("odd")
                    match["odd"]=1.0
                    match["void"]=True
                    match["void_reason"]="did_not_play"
                    match["result_status"]="pogođen"
                    match.pop("final_points",None)
                    legs.append("pogođen")
                    continue
                if not isinstance(rec.get("player_points"),int):
                    legs.append(None)
                    continue
                if match.get("void"):
                    raise ValueError("Previously confirmed VOID contradicts a scored game")
                points=rec["player_points"]
                line=float(match["points_line"])
                side=match.get("pick")
                outcome=("pogođen" if points>line else "promašen" if rec["state"]=="final" else None) if side=="over" else ("pogođen" if rec["state"]=="final" and points<line else "promašen" if points>=line else None)
                legs.append(outcome)
                if rec["state"]=="final" and outcome is not None:
                    if match.get("result_status") in ("pogođen","promašen") and match["result_status"]!=outcome:
                        raise ValueError("Locked NBA player result conflict")
                    match["result_status"]=outcome
                    match["final_points"]=points
                continue
            score=str(rec.get("score",""))
            parts=score.split(":")
            if len(parts)!=2 or any(not x.isdigit() for x in parts):
                legs.append(None)
                continue
            if rec.get("state")=="final" and rec.get("result_status") in ("pogođen","promašen"):
                legs.append(rec["result_status"])
                if match.get("result_status") in ("pogođen","promašen") and match["result_status"]!=rec["result_status"]:
                    raise ValueError("Locked match result conflict")
                if match.get("final_score") and match["final_score"]!=score:
                    raise ValueError("Locked score conflict")
                match["result_status"]=rec["result_status"]
                match["final_score"]=score
            elif early_goals_hit(match,rec):
                legs.append("pogođen")
            else:
                legs.append(None)
        if not legs:
            continue
        # Adjust effective ticket odds once, and only for verified VOID legs.
        if any(m.get("void") for m in ticket.get("matches",[])):
            if ticket.get("original_odds") is None:
                ticket["original_odds"]=ticket.get("odds")
            adjusted=Decimal(1)
            for leg in ticket["matches"]:
                adjusted*=amount(leg["odd"])
            ticket["odds"]=float(cents(adjusted))
        # A single final loss makes the ticket irreversibly lost.
        if "promašen" in legs:
            expected="izgubljen"
        elif all(x=="pogođen" for x in legs):
            expected="dobitan"
        else:
            expected=None
        if ticket["status"] in ("dobitan","izgubljen"):
            if expected and expected!=ticket["status"]:
                raise ValueError("Locked ticket conflicts with verified scores")
            if ticket["status"]=="dobitan" and any(m.get("void") for m in ticket.get("matches",[])):
                ticket["payout"]=float(cents(amount(ticket["stake"])*amount(ticket["odds"])))
            continue
        if expected is None:
            continue
        ticket["status"]=expected
        ticket["settled_at_utc"]=updated.isoformat()
        ticket["payout"]=float(cents(amount(ticket["stake"])*amount(ticket["odds"]))) if expected=="dobitan" else 0.0
        newly_settled.append(str(ticket["id"]))
    payouts=sum((cents(amount(t.get("payout",0))) for t in original.get("tickets",[])
                 if t.get("status")=="dobitan"),Decimal(0))
    available=cents(base+payouts)
    original["bank_after_stakes"]=float(cents(base))
    original["bank_after"]=float(available)
    original["total_payout"]=float(cents(payouts))
    original.pop("provisional_payout",None)
    original.pop("provisional_ticket_ids",None)
    def leg_finished(t, i, m):
        rec=outcomes.get((str(t.get("id")),i))
        if not rec or rec.get("state")!="final" or rec.get("home")!=m.get("home") or rec.get("away")!=m.get("away"):
            return False
        if m.get("sport")=="basketball" and m.get("market")=="player_points":
            return (rec.get("source") in ("espn-public-unofficial","nba-official-scorers-report")
                    and rec.get("sport")=="basketball"
                    and str(rec.get("event_id"))==str(m.get("espn_event_id"))
                    and str(rec.get("player_id"))==str(m.get("player_id"))
                    and ((rec.get("void") is True and rec.get("void_reason")=="did_not_play" and
                          rec.get("player_points") is None and
                          (rec.get("source")!="nba-official-scorers-report" or bool(rec.get("verification_source_url"))))
                         or isinstance(rec.get("player_points"),int)))
        return rec.get("source")=="espn-public-unofficial" and rec.get("result_status") in ("pogođen","promašen")
    # Closing a whole ticket may be irreversible before all legs have finished.
    # Do not archive a card until EVERY individual result is final, including VOID.
    complete=all(t.get("status") in ("dobitan","izgubljen","preskočen")
                 and all(leg_finished(t,i,m) for i,m in enumerate(t.get("matches",[])))
                 for t in original.get("tickets",[]))
    original["settled"]=bool(complete)
    original["provisional"]=not complete
    original["net_change"]=float(cents(available-before)) if complete else None
    return original,newly_settled

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--publication",default="data.json")
    parser.add_argument("--scores",default="live-scores.json")
    args=parser.parse_args()
    file=Path(args.publication)
    original_text=file.read_text(encoding="utf-8")
    published=json.loads(original_text)
    snapshot=json.loads(Path(args.scores).read_text(encoding="utf-8"))
    updated,settled=settle(published,snapshot)
    if updated!=published:
        file.write_text(json.dumps(updated,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("VIRTUAL_SETTLEMENT",json.dumps({"newly_settled":settled,
        "all_settled":updated["settled"],"total_payout":updated["total_payout"],
        "bank":updated["bank_after"]}))

if __name__=="__main__":
    main()
