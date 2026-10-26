#!/usr/bin/env python3
"""Settle published *virtual* tickets from unambiguous verified final score data.

Idempotent: derives the balance from original after-stakes balance plus the
payouts of settled tickets. No event is paid twice on repeated execution.
Does not modify published selections, odds or stakes; does not edit archive.
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
    provisional_credits = {}
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
        if ticket.get("status") in ("preskočen",):
            continue
        if ticket.get("status") not in ("objavljen","dobitan","izgubljen"):
            continue
        observations=[]
        for index,match in enumerate(ticket.get("matches",[])):
            rec = outcomes.get((str(ticket["id"]),index))
            if not rec or rec.get("home")!=match.get("home") or rec.get("away")!=match.get("away"):
                observations.append(None)
                continue
            if rec.get("state")!="final" or rec.get("source")!="espn-public-unofficial":
                observations.append(None)
                continue
            if rec.get("result_status") not in ("pogođen","promašen"):
                observations.append(None)
                continue
            score = str(rec.get("score",""))
            parts = score.split(":")
            if len(parts)!=2 or any(not p.isdigit() for p in parts):
                observations.append(None)
                continue
            observations.append(rec)
        if not observations or any(o is None for o in observations):
            if ticket["status"] == "objavljen" and ticket.get("matches") and all(
                (observations[i] is not None and observations[i]["result_status"] == "pogođen")
                or early_goals_hit(match, outcomes.get((str(ticket["id"]), i)))
                for i, match in enumerate(ticket["matches"])
            ):
                provisional_credits[str(ticket["id"])] = cents(amount(ticket["stake"])*amount(ticket["odds"]))
            continue
        expected = "dobitan" if all(x["result_status"]=="pogođen" for x in observations) else "izgubljen"
        if ticket["status"] in ("dobitan","izgubljen") and ticket["status"]!=expected:
            raise ValueError("Locked ticket conflicts with verified scores")
        if ticket["status"]=="objavljen":
            ticket["status"]=expected
            ticket["settled_at_utc"]=updated.isoformat()
            newly_settled.append(str(ticket["id"]))
        for index,record in enumerate(observations):
            match=ticket["matches"][index]
            if match.get("result_status") in ("pogođen","promašen") and match["result_status"]!=record["result_status"]:
                raise ValueError("Locked match result conflict")
            if match.get("final_score") and match["final_score"]!=record["score"]:
                raise ValueError("Locked score conflict")
            match["result_status"]=record["result_status"]
            match["final_score"]=record["score"]
        expected_payout = cents(amount(ticket["stake"])*amount(ticket["odds"])) if expected=="dobitan" else Decimal(0)
        if "payout" in ticket and cents(amount(ticket["payout"]))!=expected_payout:
            raise ValueError("Existing payout mismatch")
        ticket["payout"]=float(expected_payout)
    payouts=sum((cents(amount(t.get("payout",0))) for t in original.get("tickets",[])
                 if t.get("status")=="dobitan"),Decimal(0))
    provisional_total=sum(provisional_credits.values(),Decimal(0))
    available=cents(base+payouts+provisional_total)
    original["bank_after_stakes"]=float(cents(base))
    original["bank_after"]=float(available)
    original["total_payout"]=float(cents(payouts+provisional_total))
    original["provisional_payout"]=float(cents(provisional_total))
    original["provisional_ticket_ids"]=sorted(provisional_credits)
    complete=all(t.get("status") in ("dobitan","izgubljen","preskočen")
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
